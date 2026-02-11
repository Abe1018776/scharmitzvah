#!/usr/bin/env python3
"""Generate rich index entries by analyzing book content with Claude via OpenRouter."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai package required. Install with: pip install openai")
    sys.exit(1)

# Default model: Claude Opus 4.6 via OpenRouter
DEFAULT_MODEL = "anthropic/claude-opus-4-6"

SYSTEM_PROMPT = """You are an expert in Torah literature and Jewish scholarly texts. You are helping create a מפתח (analytical index) for ספר שכר מצוה, a compilation of sources answering the question: when and why can a person receive שכר מצוה (reward for mitzvos) in עולם הזה (this world)?

For each entry, you will receive the entry number, title, and source texts. You must produce THREE fields in Hebrew:

1. **תמצית הענין** (Summary): A concise 15-30 word summary of the position/approach. This should be a clear declarative statement of WHAT this source says about receiving schar in olam hazeh. Write in the same scholarly Hebrew style as the source text.

2. **הטעם** (Reason): The logical/philosophical reasoning — WHY this approach works. Extract the causal argument ("because X, therefore Y"). This should explain the mechanism or logic, not just repeat the summary.

3. **מקור** (Source): List the source citations. Extract these from the parenthetical references in the text. List primary source first, then secondary. Use the exact names as they appear in the text.

IMPORTANT RULES:
- Write ONLY in Hebrew
- Match the scholarly tone and style of the source text
- Keep תמצית הענין concise (15-30 words max)
- Make הטעם explain the WHY, not repeat the WHAT
- For מקור, extract only the sefer names from parenthetical citations
- If multiple sources say similar things, synthesize into one unified summary and reason
- Output valid JSON only"""

USER_PROMPT_TEMPLATE = """Analyze this entry from ספר שכר מצוה and produce the index fields.

Entry number: {number}
Title: {title}

Source texts:
{sources}

Respond with ONLY a JSON object (no markdown, no explanation):
{{
  "summary": "תמצית הענין text here",
  "reason": "הטעם text here",
  "source": "מקור text here"
}}"""


def build_source_text(entry):
    """Build combined source text from entry sources."""
    parts = []
    for s in entry['sources']:
        text = s['text']
        if s.get('citation'):
            text = text.rstrip()
            if not text.endswith(')'):
                text += f" ({s['citation']})"
        parts.append(text)
    return '\n'.join(parts)


def generate_entry(client, entry, model=DEFAULT_MODEL):
    """Generate index fields for a single entry."""
    source_text = build_source_text(entry)

    if not source_text.strip():
        return {
            'summary': entry['title'],
            'reason': '',
            'source': '',
        }

    prompt = USER_PROMPT_TEMPLATE.format(
        number=entry['number'],
        title=entry['title'],
        sources=source_text,
    )

    response = client.chat.completions.create(
        model=model,
        max_tokens=1000,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )

    text = response.choices[0].message.content.strip()
    # Strip markdown code fences if present
    if text.startswith('```'):
        text = text.split('\n', 1)[1]
        if text.endswith('```'):
            text = text[:-3]
        text = text.strip()

    try:
        result = json.loads(text)
        return {
            'summary': result.get('summary', ''),
            'reason': result.get('reason', ''),
            'source': result.get('source', ''),
        }
    except json.JSONDecodeError:
        print(f"  Warning: Failed to parse JSON for entry {entry['number']}")
        print(f"  Response: {text[:200]}")
        return {
            'summary': entry['title'],
            'reason': '',
            'source': text,
        }


def load_existing_index(path):
    """Load existing index.json if it exists."""
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'chapters': []}


def find_existing_entry(index_data, chapter_name, section_name, entry_number):
    """Check if an entry already exists in the index."""
    for ch in index_data['chapters']:
        if ch['name'] != chapter_name:
            continue
        for sec in ch['sections']:
            if sec['section_name'] != section_name:
                continue
            for entry in sec['entries']:
                if entry['number'] == entry_number:
                    return True
    return False


def main():
    parser = argparse.ArgumentParser(description='Generate index entries using Claude via OpenRouter')
    parser.add_argument('--chapter', type=int, help='Process only this chapter (1-6)')
    parser.add_argument('--section', type=str, help='Process only this section name')
    parser.add_argument('--model', default=DEFAULT_MODEL, help=f'Model to use (default: {DEFAULT_MODEL})')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between API calls (seconds)')
    parser.add_argument('--force', action='store_true', help='Regenerate existing entries')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed without calling API')
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent
    parsed_path = repo_root / 'data' / 'book_parsed.json'
    index_path = repo_root / 'data' / 'index.json'

    if not parsed_path.exists():
        print("Error: data/book_parsed.json not found. Run parse_book.py first.")
        sys.exit(1)

    with open(parsed_path, 'r', encoding='utf-8') as f:
        book_data = json.load(f)

    index_data = load_existing_index(index_path)

    if not args.dry_run:
        api_key = os.environ.get('OPENROUTER_API_KEY')
        if not api_key:
            print("Error: OPENROUTER_API_KEY environment variable not set.")
            print("  export OPENROUTER_API_KEY=your_key_here")
            sys.exit(1)

        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        print(f"Using model: {args.model} via OpenRouter")

    total_processed = 0
    total_skipped = 0

    for ch_idx, chapter in enumerate(book_data['chapters']):
        if args.chapter and (ch_idx + 1) != args.chapter:
            continue

        # Find or create chapter in index
        index_chapter = None
        for ic in index_data['chapters']:
            if ic['name'] == chapter['name']:
                index_chapter = ic
                break
        if not index_chapter:
            index_chapter = {
                'name': chapter['name'],
                'title': chapter['title'],
                'sections': [],
            }
            index_data['chapters'].append(index_chapter)

        for section in chapter['sections']:
            if args.section and section['section_name'] != args.section:
                continue

            # Find or create section in index
            index_section = None
            for is_ in index_chapter['sections']:
                if is_['section_name'] == section['section_name']:
                    index_section = is_
                    break
            if not index_section:
                index_section = {
                    'section_name': section['section_name'],
                    'entries': [],
                }
                index_chapter['sections'].append(index_section)

            print(f"\n{'='*60}")
            print(f"Chapter: {chapter['name']} — {chapter['title']}")
            print(f"Section: {section['section_name'] or '(default)'}")
            print(f"Entries: {len(section['entries'])}")
            print(f"{'='*60}")

            for entry in section['entries']:
                # Check if already processed
                if not args.force and find_existing_entry(
                    index_data, chapter['name'], section['section_name'], entry['number']
                ):
                    total_skipped += 1
                    print(f"  Skip {entry['number']}. {entry['title'][:50]} (already exists)")
                    continue

                if args.dry_run:
                    sources_text = build_source_text(entry)
                    print(f"  Would process: {entry['number']}. {entry['title'][:50]} "
                          f"({len(entry['sources'])} sources, {len(sources_text)} chars)")
                    total_processed += 1
                    continue

                print(f"  Processing {entry['number']}. {entry['title'][:50]}...")

                try:
                    result = generate_entry(client, entry, model=args.model)
                except Exception as e:
                    print(f"  Error: {e}")
                    print(f"  Skipping entry {entry['number']}...")
                    continue

                index_entry = {
                    'number': entry['number'],
                    'title': entry['title'],
                    'summary': result['summary'],
                    'reason': result['reason'],
                    'source': result['source'],
                }

                # Remove old entry if force-regenerating
                index_section['entries'] = [
                    e for e in index_section['entries']
                    if e['number'] != entry['number']
                ]
                index_section['entries'].append(index_entry)

                print(f"    Summary: {result['summary'][:60]}...")
                print(f"    Reason: {result['reason'][:60]}...")
                print(f"    Source: {result['source'][:60]}")

                total_processed += 1

                # Save after each entry (for resume support)
                with open(index_path, 'w', encoding='utf-8') as f:
                    json.dump(index_data, f, ensure_ascii=False, indent=2)

                time.sleep(args.delay)

    print(f"\nDone. Processed: {total_processed}, Skipped: {total_skipped}")
    if not args.dry_run:
        print(f"Index saved to {index_path}")


if __name__ == '__main__':
    main()

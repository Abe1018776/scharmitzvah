#!/usr/bin/env python3
"""Parse the Sefer Schar Mitzvah book content docx into structured JSON."""

import json
import re
import sys
from pathlib import Path
from docx import Document


# Patterns
# Entry numbers: Hebrew letter(s) followed by a PERIOD then space
# e.g. "א. על כל מצוה" or "קלה. על חינוך"
HEBREW_NUM = re.compile(r'^([א-ת]{1,4})\.\s+(.+)')
# Also match entries without period but with Heading 2 style (handled in code)
PAGE_MARKER = re.compile(r'^—\s*Page\s+\d+\s*—$')
PAGE_HEADER = re.compile(r'^[א-ת]+ שכר .+ מצוה$')
CHAPTER_PATTERN = re.compile(r'^פרק\s+(ראשון|שני|שלישי|רביעי|חמישי|ששי)')
CITATION_PATTERN = re.compile(r'\(([^)]+)\)\s*$')

# Valid Hebrew numeral prefixes (to filter out regular words that match the pattern)
# Single units: א-ט
# Tens: י,כ,ל,מ,נ,ס,ע,פ,צ
# Hundreds: ק,ר,ש,ת
# Common combinations: יא-יט, כ-כט, ל-לט, etc.
def is_valid_hebrew_numeral(s):
    """Check if a string is a valid Hebrew numeral (not a regular word)."""
    if len(s) == 1:
        return True  # Single letters are always valid numerals
    # Known non-numeral words that might match
    NON_NUMERALS = {
        'מקור', 'דשכר', 'דהא', 'דהיינו', 'דוקא', 'דאף', 'דבר', 'דעל',
        'יש', 'כי', 'כל', 'אף', 'אך', 'אבל', 'גם', 'רק',
        'טובת', 'טעם', 'טורח',
        'לכן', 'לכך', 'למה', 'לבד',
        'עוד', 'עלמא',
        'שהוא', 'שכר', 'שכל', 'שאם',
        'והנה', 'ולכך', 'ולכן',
        'כתבו', 'כיון', 'כגון', 'כדי',
        'בכל', 'באלו',
        'דאגב', 'דהנה',
        'עבור', 'ואמר',
        'איתא', 'נראה',
    }
    if s in NON_NUMERALS:
        return False
    # Standard Hebrew numeral patterns (covers א through תתקצט)
    # Most entries go up to ~קמה (145), so be generous
    return True

# Known chapter titles (second line after "פרק X")
CHAPTER_TITLES = {
    'שכר על כל מצוה',
    'סוגי מצוות',
    'מצוות והנהגות מיוחדות',
    'אנשים, זמנים ומקומות מסויימים',
    'ענינים מיוחדים',
    'אופנים בקיום המצוה',
}

# Known sub-section headers (appear without numbers, mark topic changes)
KNOWN_SUBSECTIONS = {
    'מ"ע ול"ת מיוחדות', "מ״ע ול״ת מיוחדות",
    'תורה', 'קר"ש תפלה וברכות', 'קר״ש תפלה וברכות',
    'שבת, מועדים וזמנים', 'שבת מועדים וזמנים',
    'אהבה ויראה', 'אמונה',
    'צדקה וגמילות חסדים', 'חינוך',
    'אנשים מסויימים', 'זמנים מסויימים', 'מקום מסויים',
    'זכות אבות', 'ישראל', 'יסורים', 'כבוד שמים',
    'מזכה הרבים', 'מחשבה ורצון', 'משא ומתן',
    'מתנת שכר', 'נסיון', 'עניו', 'עבירה', 'עבודה',
    'רוצה', 'רשות לשם מצוה', 'שלום', 'תשובה', 'שונות',
    'על פרטים שבכל מצוה',
    'רצון והשתוקקות', 'מקבל', 'ממציא עצמו',
    'טירחא', 'הכנה', 'לומד', 'שמחה', 'זריזות',
    'הידור וכבוד', 'מסי"נ', 'מסי״נ', 'כולל',
    'לשם המצוה', 'צער והעדר תענוג', 'תוספות ברכה',
    'עזר מהי',
}

# Sections to skip (notes/appendices at end of book)
SKIP_SECTIONS = {
    'הערות מחכימות', 'בעניני שכר מצוה', 'הערות בענין שכר מצוה',
    'הערות', 'הערה כללית כעין מבוא', 'מצוה גוררת מצוה',
    'מקור המצוה',
}


def is_page_marker(text):
    return bool(PAGE_MARKER.match(text))


def is_page_header(text):
    """Running page headers like 'כו שכר פרק ראשון מצוה'"""
    return bool(PAGE_HEADER.match(text))


def is_subsection_header(text):
    """Check if text is a known sub-section header."""
    return text in KNOWN_SUBSECTIONS


def is_skip_section(text):
    return text in SKIP_SECTIONS


def extract_citation(text):
    """Extract citation from parentheses at end of text."""
    m = CITATION_PATTERN.search(text)
    if m:
        return m.group(1).strip()
    return None


def parse_book(docx_path):
    doc = Document(docx_path)

    chapters = []
    current_chapter = None
    current_section = None
    current_entry = None
    skip_mode = False

    for para in doc.paragraphs:
        style = para.style.name if para.style else 'None'
        text = para.text.strip()

        if not text:
            continue

        # Skip page markers and running headers
        if is_page_marker(text) or is_page_header(text):
            continue

        # Check for chapter start
        if CHAPTER_PATTERN.match(text):
            # Save previous chapter
            if current_entry and current_section:
                current_section['entries'].append(current_entry)
                current_entry = None
            if current_section and current_chapter:
                current_chapter['sections'].append(current_section)
                current_section = None
            if current_chapter:
                chapters.append(current_chapter)

            current_chapter = {
                'name': text,
                'title': '',
                'sections': [],
            }
            current_section = {'section_name': None, 'entries': []}
            current_entry = None
            skip_mode = False
            continue

        # Check for chapter title
        if text in CHAPTER_TITLES and current_chapter and not current_chapter['title']:
            current_chapter['title'] = text
            continue

        # Check for skip sections (notes/appendices)
        if is_skip_section(text):
            skip_mode = True
            continue

        if skip_mode:
            continue

        # Check for sub-section header
        if is_subsection_header(text) or (style == 'Heading 2' and not HEBREW_NUM.match(text) and not CHAPTER_PATTERN.match(text) and text not in CHAPTER_TITLES):
            if not is_skip_section(text):
                # Save current entry
                if current_entry and current_section:
                    current_section['entries'].append(current_entry)
                    current_entry = None
                # Save current section, start new one
                if current_section and current_chapter:
                    if current_section['entries']:
                        current_chapter['sections'].append(current_section)
                current_section = {'section_name': text, 'entries': []}
                continue

        # Check for entry header (numbered with Hebrew letters)
        m = HEBREW_NUM.match(text)
        if m and is_valid_hebrew_numeral(m.group(1)):
            num = m.group(1)
            title = m.group(2).strip()

            # Save previous entry
            if current_entry and current_section:
                current_section['entries'].append(current_entry)

            if current_section is None and current_chapter:
                current_section = {'section_name': None, 'entries': []}

            current_entry = {
                'number': num,
                'title': title,
                'sources': [],
            }
            continue

        # Regular text — source content for current entry
        if current_entry:
            # Skip "מקור המצוה:" prefix
            source_text = text
            if source_text.startswith('מקור המצוה:'):
                source_text = source_text[len('מקור המצוה:'):].strip()

            if source_text:
                citation = extract_citation(source_text)
                current_entry['sources'].append({
                    'text': source_text,
                    'citation': citation,
                })

    # Save final entry/section/chapter
    if current_entry and current_section:
        current_section['entries'].append(current_entry)
    if current_section and current_chapter:
        if current_section['entries']:
            current_chapter['sections'].append(current_section)
    if current_chapter:
        chapters.append(current_chapter)

    return {'chapters': chapters}


def print_summary(data):
    total_entries = 0
    for ch in data['chapters']:
        ch_entries = sum(len(s['entries']) for s in ch['sections'])
        total_entries += ch_entries
        print(f"\n{ch['name']} — {ch['title']} ({ch_entries} entries)")
        for sec in ch['sections']:
            sec_name = sec['section_name'] or '(default)'
            print(f"  {sec_name}: {len(sec['entries'])} entries")
            for entry in sec['entries'][:3]:
                print(f"    {entry['number']}. {entry['title'][:60]} ({len(entry['sources'])} sources)")
            if len(sec['entries']) > 3:
                print(f"    ... and {len(sec['entries']) - 3} more")
    print(f"\nTotal entries: {total_entries}")


def main():
    repo_root = Path(__file__).parent.parent
    docx_path = repo_root / 'schar mitzvah actual book content (3).docx'
    output_path = repo_root / 'data' / 'book_parsed.json'

    if not docx_path.exists():
        print(f"Error: {docx_path} not found")
        sys.exit(1)

    print(f"Parsing {docx_path.name}...")
    data = parse_book(str(docx_path))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Saved to {output_path}")
    print_summary(data)


if __name__ == '__main__':
    main()

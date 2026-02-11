# Sefer Schar Mitzvah — Mafteichos Index Project

## Overview
This project generates a rich analytical index (מפתחות) for ספר שכר מצוה — a compilation of sources answering: **when and why can a person receive שכר מצוה in עולם הזה?**

The book contains ~466 entries across 6 chapters. Each entry cites sources with different approaches to this question. The index transforms each entry into a 4-column table with summary, reasoning, and source citations.

## Index Format (4 columns)

| Column | Header | Content |
|--------|--------|---------|
| 1 | האופן | Sequential Hebrew letter number (א, ב, ג...) |
| 2 | תמצית הענין | Concise summary of the position (15-30 words) |
| 3 | הטעם | The reasoning — WHY this approach allows schar in olam hazeh |
| 4 | מקור | Source citations extracted from the text |

### Example (from sample):
| האופן | תמצית הענין | הטעם | מקור |
|-------|-------------|------|------|
| א. | בזכות האבות אוכלים הבנים בעוה"ז | שכר מצוה של האדם עצמו אינו רק בעולם הבא אולם זכות אבות שמור לבנים גם בעוה"ז | ערבי נחל. החיד"א כסא דוד. |

## Scripts

### 1. Parse book content
```bash
python scripts/parse_book.py
```
Parses the book docx into `data/book_parsed.json` with structured entries.

### 2. Generate index entries (requires OPENROUTER_API_KEY)
```bash
# Process all chapters:
python scripts/generate_index.py

# Process specific chapter:
python scripts/generate_index.py --chapter 5

# Process specific section:
python scripts/generate_index.py --chapter 5 --section "זכות אבות"

# Dry run (see what would be processed):
python scripts/generate_index.py --dry-run

# Force regenerate existing entries:
python scripts/generate_index.py --force
```
Uses Claude Opus 4.6 via OpenRouter. Sends each entry to the API, saves results to `data/index.json`. Supports resume — skips already-processed entries.

### 3. Generate formatted docx
```bash
python scripts/generate_docx.py
```
Converts `data/index.json` into a formatted RTL Hebrew docx at `output/mafteichos.docx`.

## Workflow for Processing New Text
1. Place new digitized text (txt/docx) in `input/`
2. Run `python scripts/parse_book.py` to update `data/book_parsed.json`
3. Run `python scripts/generate_index.py` to generate index entries
4. Run `python scripts/generate_docx.py` to produce the formatted output
5. Review `output/mafteichos.docx`

## Indexing Methodology

When analyzing source text to create index entries, follow these rules:

### תמצית הענין (Summary)
- Distill the position into a clear, concise 15-30 word Hebrew statement
- Use declarative language — state WHAT this source says about schar in olam hazeh
- Match the scholarly Hebrew tone of the original text

### הטעם (Reason)
- Extract the causal/logical argument — WHY according to this source
- Use connective language: כיון ש..., משום ד..., שהרי...
- Don't repeat the summary — explain the underlying mechanism
- If multiple sources are cited, synthesize into one unified reasoning

### מקור (Source)
- Extract sefer names from parenthetical citations in the text
- List primary source first, secondary sources after
- Use exact names as they appear: e.g., "ערבי נחל", "חת"ס פר' פנחס"

## File Structure
```
scharmitzvah/
├── CLAUDE.md                    ← You are here
├── input/                       ← Digitized text goes here
├── data/
│   ├── book_parsed.json         ← Parsed book entries
│   └── index.json               ← Generated index entries
├── output/
│   └── mafteichos.docx          ← Formatted output
├── scripts/
│   ├── parse_book.py            ← Parse book docx
│   ├── generate_index.py        ← Generate index with Claude API
│   ├── generate_docx.py         ← Generate formatted docx
│   └── requirements.txt
└── sample/
    └── __ ספר שכר מצוה מפתח דוגמא_.docx  ← Reference sample
```

## Setup
```bash
pip install -r scripts/requirements.txt
export OPENROUTER_API_KEY=your_key_here
```

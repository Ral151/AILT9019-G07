"""
corpus_processor.py - Offline Corpus Construction Step 2

Reads the cleaned .txt documents from corpus_raw/, splits each document into
paragraphs, assigns a stable paragraph number within each source, and writes
the unified encyclopedia to hku_recycling_corpus.json.

Each encyclopedia entry looks like:
    {
      "id": "re_facilities#3",
      "source": "re_facilities",
      "source_title": "re Facilities - ...",
      "url": "https://...",
      "organization": "HKU Waste Reduction",
      "paragraph": 3,
      "tags": ["plastic", "smart bin"],
      "text": "..."
    }

The "id" is the citation anchor used by the online pipeline (source + paragraph
number).

Usage:
    python corpus_processor.py
"""

import json
import os
import re
import sys


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES_FILE = os.path.join(BASE_DIR, "sources.json")
RAW_DIR = os.path.join(BASE_DIR, "corpus_raw")
OUTPUT_FILE = os.path.join(BASE_DIR, "hku_recycling_corpus.json")


# Keyword -> tag mapping used to lightly tag paragraphs for better retrieval.
TAG_RULES = [
    (["plastic", "pet", "polythene", "plastic bag", "plastic bottle", "foam", "eps", "polystyrene"], "plastic"),
    (["paper", "newspaper", "cardboard", "carton box", "magazine", "textbook", "a4"], "paper"),
    (["metal", "aluminium", "aluminum", "tin can", "can"], "metal"),
    (["glass", "wine bottle", "jam jar", "glass bottle"], "glass"),
    (["tetra pak", "milk carton", "beverage carton", "juice box"], "tetra pak"),
    (["battery", "rechargeable", "power bank"], "battery"),
    (["smart recycling bin", "smart bin"], "smart bin"),
    (["re kiosk", "kiosk"], "re kiosk"),
    (["greenu", "green u", "points", "reward"], "greenu"),
    (["glass bottle", "glass"], "glass"),
]


def load_sources():
    with open(SOURCES_FILE, "r", encoding="utf-8") as f:
        return {s["id"]: s for s in json.load(f)["sources"]}


def split_paragraphs(text):
    """Split text into non-empty paragraphs (double newline or heading-style lines)."""
    # Normalise line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Split on blank lines
    raw_paras = re.split(r"\n\s*\n", text)
    paras = []
    for p in raw_paras:
        p = p.strip()
        if not p:
            continue
        # Keep single headings as their own paragraph
        paras.append(p)
    return paras


def assign_tags(text):
    lower = text.lower()
    tags = set()
    for keywords, tag in TAG_RULES:
        if any(kw in lower for kw in keywords):
            tags.add(tag)
    return sorted(tags)


def process_document(source_id, source_meta, text):
    paragraphs = split_paragraphs(text)
    entries = []
    for idx, para in enumerate(paragraphs, start=1):
        entries.append({
            "id": f"{source_id}#{idx}",
            "source": source_id,
            "source_title": source_meta.get("title", ""),
            "url": source_meta.get("url", ""),
            "organization": source_meta.get("organization", ""),
            "paragraph": idx,
            "tags": assign_tags(para),
            "text": para,
        })
    return entries


def main():
    sources = load_sources()
    all_entries = []

    print(f"corpus_processor: scanning {RAW_DIR}")
    txt_files = sorted(f for f in os.listdir(RAW_DIR) if f.endswith(".txt"))
    if not txt_files:
        print("ERROR: No .txt files found in corpus_raw/. Run collect_docs.py first.",
              file=sys.stderr)
        sys.exit(1)

    for fname in txt_files:
        source_id = fname[:-4]  # strip .txt
        if source_id not in sources:
            print(f"  [WARN] {fname} has no matching entry in sources.json; skipping.")
            continue
        path = os.path.join(RAW_DIR, fname)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        entries = process_document(source_id, sources[source_id], text)
        all_entries.extend(entries)
        print(f"  [{source_id}] {len(entries)} paragraph(s) from {fname}")

    # Build the encyclopedia object
    encyclopedia = {
        "name": "HKU Recycling Encyclopedia",
        "version": "1.0",
        "description": "Built from official HKU recycling documents. Each entry is a paragraph with a stable citation id (source + paragraph number).",
        "entry_count": len(all_entries),
        "sources": list({e["source"] for e in all_entries}),
        "entries": all_entries,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(encyclopedia, f, ensure_ascii=False, indent=2)

    print(f"\ncorpus_processor: wrote {len(all_entries)} entries to {OUTPUT_FILE}")
    print("Offline corpus construction complete.")


if __name__ == "__main__":
    main()

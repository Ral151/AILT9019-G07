"""
collect_docs.py - Offline Corpus Construction Step 1

Fetches official HKU recycling documents from the URLs listed in sources.json,
cleans the HTML to plain text, and saves each document as a .txt file under
corpus_raw/. If a URL cannot be fetched (network error, blocked, etc.), the
script falls back to the manually-prepared .txt file specified by
"fallback_file" in sources.json. This matches the project rule:
"爬不动时手动另存为 .txt" (if crawling fails, manually save as .txt).

Usage:
    python collect_docs.py
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error
from html.parser import HTMLParser


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCES_FILE = os.path.join(BASE_DIR, "sources.json")
RAW_DIR = os.path.join(BASE_DIR, "corpus_raw")


class HTMLTextExtractor(HTMLParser):
    """Minimal HTML-to-text extractor that strips tags and scripts/styles."""

    def __init__(self):
        super().__init__()
        self._text_parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip == 0:
            self._text_parts.append(data)

    def get_text(self):
        text = "".join(self._text_parts)
        # Collapse whitespace but preserve paragraph breaks (blank lines)
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def fetch_url(url, timeout=15):
    """Fetch a URL and return decoded text, or None on failure."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            )
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        print(f"  [WARN] Failed to fetch {url}: {e}")
        return None


def clean_html(html_text):
    """Convert raw HTML to cleaned plain text."""
    extractor = HTMLTextExtractor()
    try:
        extractor.feed(html_text)
    except Exception:
        pass
    text = extractor.get_text()
    # Remove common boilerplate line fragments that add no value
    noise = [
        "Click for more details",
        "Find bin",
        "Download printable version",
        "Download PDF here",
        "Photo Guide",
        "Final check before recycling",
    ]
    for n in noise:
        text = text.replace(n, "")
    return text


def has_boilerplate(text):
    """Return True if the fetched text looks like it still contains navigation/boilerplate."""
    markers = [
        "top of page",
        "bottom of page",
        "Use tab to navigate through the menu",
        "Academic Freedom Policy",
        "Code of Conduct",
        "Rent a",
        "Homepage",
    ]
    return any(m in text for m in markers)


def main():
    os.makedirs(RAW_DIR, exist_ok=True)

    with open(SOURCES_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)

    sources = config.get("sources", [])
    print(f"collect_docs: found {len(sources)} source(s) in sources.json")

    results = []
    for src in sources:
        sid = src["id"]
        url = src["url"]
        fallback = os.path.join(BASE_DIR, src.get("fallback_file", ""))
        out_path = os.path.join(RAW_DIR, f"{sid}.txt")

        print(f"\n[{sid}] {url}")
        html = fetch_url(url)
        used_fallback = False
        if html:
            text = clean_html(html)
            if len(text.strip()) < 50:  # too little text -> treat as failure
                print(f"  [WARN] Fetched text too short ({len(text.strip())} chars), using fallback.")
                used_fallback = True
            elif has_boilerplate(text):
                print(f"  [WARN] Fetched text contains navigation boilerplate, using fallback.")
                used_fallback = True
            else:
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(text)
                print(f"  [OK] Saved {len(text)} chars to {out_path}")
                results.append((sid, "fetched", out_path))
                continue

        if used_fallback or not html:
            if os.path.exists(fallback):
                with open(fallback, "r", encoding="utf-8") as f:
                    text = f.read()
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(text)
                print(f"  [FALLBACK] Using {fallback} ({len(text)} chars)")
                results.append((sid, "fallback", out_path))
            else:
                print(f"  [ERROR] No fallback file found at {fallback}")
                results.append((sid, "failed", None))

    print("\n=== collect_docs summary ===")
    ok = sum(1 for _, status, _ in results if status in ("fetched", "fallback"))
    print(f"Successfully prepared {ok}/{len(results)} document(s).")
    for sid, status, path in results:
        print(f"  {sid}: {status}" + (f" -> {path}" if path else ""))

    if ok == 0:
        print("ERROR: No documents could be prepared. Aborting.", file=sys.stderr)
        sys.exit(1)

    print("\nNext step: run corpus_processor.py to build the encyclopedia JSON.")


if __name__ == "__main__":
    main()

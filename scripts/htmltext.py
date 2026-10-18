"""Extract visible text lines from a saved HTML snapshot (used by ingest.py).

Lines are normalised the same way as corpus/chunks/*.txt so that ingest can
prove every chunk line of an `html_text` source is copied from the snapshot.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

_BLOCK_TAGS = {"p", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "br", "tr", "section", "ul", "ol"}
_SKIP_TAGS = {"script", "style", "noscript", "svg"}


def normalise_line(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    return re.sub(r"\s+", " ", text).strip()


class _Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in _SKIP_TAGS:
            self._skip += 1
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip:
            self._skip -= 1
        if tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


def html_lines(path: Path) -> list[str]:
    parser = _Extractor()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    lines = (normalise_line(line) for line in "".join(parser.parts).split("\n"))
    return [line for line in lines if line]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    for i, line in enumerate(html_lines(Path(sys.argv[1])), 1):
        print(f"{i:4d} {line}")

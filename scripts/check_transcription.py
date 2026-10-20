"""Cross-check each corpus source's transcription against its raw file.

Helps with the manual review step for AILT9019 Midterm Check. Two kinds of
sources exist in corpus/manifest.yaml:

* html_text           - visible text is provably copied from the saved HTML.
                        This script verifies every chunk line, line by line
                        (same proof as scripts/ingest.py).
* manual_transcription - the raw file is an image / outlined PDF with no text
                        layer, so a human typed the English text. A program
                        cannot prove this is correct, but this script extracts
                        whatever text is available (PDF text layer, then OCR
                        fallback) and does a fuzzy diff so the reviewer can
                        eyeball suspicious lines instead of re-reading the
                        whole poster.

Usage:
    python scripts/check_transcription.py              # check all sources
    python scripts/check_transcription.py --source r101_poster
    python scripts/check_transcription.py --no-ocr      # skip OCR (fast)
    python scripts/check_transcription.py --report report.txt

Exit code 0 = no transcription mismatches found (see caveats below);
1 = mismatches found. For manual_transcription sources the human verdict is
still authoritative.
"""

from __future__ import annotations

import argparse
import difflib
import sys
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from htmltext import html_lines, normalise_line  # noqa: E402

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


def _load_corpus() -> tuple[list, dict[str, list[str]]]:
    """Parse manifest.yaml + chunks/*.txt + chunks/*.yaml directly.

    Kept dependency-light so this check runs even before the full backend
    stack (Flask/torch/chromadb) is installed. Returns (sources, chunks) where
    each source is a dict from manifest.yaml and chunks maps source_id -> list
    of {"chunk_id", "text"}.
    """
    if yaml is None:
        raise SystemExit("PyYAML is required; run: pip install pyyaml")
    manifest_path = REPO_ROOT / "corpus" / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    chunks: dict[str, list] = {}
    for source in manifest["sources"]:
        sid = source["source_id"]
        txt = (REPO_ROOT / "corpus" / "chunks" / f"{sid}.txt").read_text(encoding="utf-8")
        tag_path = REPO_ROOT / "corpus" / "chunks" / f"{sid}.yaml"
        tags = yaml.safe_load(tag_path.read_text(encoding="utf-8"))
        lines = txt.splitlines()
        entries: list = []
        for e in tags["chunks"]:
            start, end = e["lines"]
            body = "\n".join(lines[start - 1 : end])
            entries.append({"chunk_id": e["id"], "text": body})
        chunks[sid] = entries
    return manifest["sources"], chunks


def _norm(s: str) -> str:
    """Normalise a raw/extracted line for comparison (looser than normalise_line)."""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("·", " ").replace("|", " ").replace("/", " ")
    s = "".join(ch for ch in s if ch.isalnum() or ch.isspace())
    return " ".join(s.split()).lower()


def _pdf_text(path: Path) -> list[str]:
    """Return the PDF text layer as lines, or [] if none / extraction fails."""
    try:
        import pdfplumber
    except ImportError:
        return []
    try:
        with pdfplumber.open(path) as pdf:
            out: list[str] = []
            for page in pdf.pages:
                text = page.extract_text() or ""
                out.extend(text.splitlines())
            return out
    except Exception:
        return []


def _ocr_text(path: Path) -> list[str]:
    """OCR an image. Requires pytesseract + the Tesseract binary."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return []
    try:
        img = Image.open(path)
        return (pytesseract.image_to_string(img) or "").splitlines()
    except Exception:
        return []


def check_html(source, chunks_by_source) -> list[str]:
    errors: list[str] = []
    sid = source["source_id"]
    raw = next(
        (REPO_ROOT / "corpus" / f for f in source["raw_files"] if str(f).endswith(".html")),
        None,
    )
    if raw is None or not raw.exists():
        return [f"{sid}: no .html snapshot found"]
    page = " " + " ".join(html_lines(raw)) + " "
    for ac in chunks_by_source[sid]:
        for line in ac["text"].splitlines():
            if normalise_line(line) not in page:
                errors.append(
                    f"{ac['chunk_id']}: line not found in snapshot: {line!r}"
                )
    return errors


def check_manual(source, chunks_by_source, use_ocr: bool) -> tuple[list[str], list[str]]:
    """Return (mismatches, info). Mismatches here are *hints* for the human."""
    mismatches: list[str] = []
    info: list[str] = []
    sid = source["source_id"]

    # Transcribed lines in chunk order (each chunk contributes its lines).
    transcript: list[str] = []
    for ac in chunks_by_source[sid]:
        transcript.extend(ac["text"].splitlines())

    # Build a pool of raw text from whatever is extractable.
    raw_pool: list[str] = []
    method = []
    for raw_rel in source["raw_files"]:
        f = REPO_ROOT / "corpus" / raw_rel
        if f.suffix.lower() == ".pdf":
            pdf_lines = _pdf_text(f)
            if pdf_lines:
                raw_pool.extend(pdf_lines)
                method.append("pdf-text")
        elif f.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            if use_ocr:
                ocr_lines = _ocr_text(f)
                if ocr_lines:
                    raw_pool.extend(ocr_lines)
                    method.append("ocr")
        # NOTE: .html snapshots are page archives, not the poster's body text,
        # so they are intentionally NOT used as comparison text here.

    if not raw_pool:
        return [], [
            f"{sid}: no text could be extracted from raw files "
            f"(method tried: {', '.join(method) or 'none'}). "
            "This source MUST be checked by eye against the image/PDF."
        ]

    raw_norm = [_norm(l) for l in raw_pool if _norm(l)]
    # token multiset so repeated words on one line still match
    raw_tokens: set[str] = set()
    for line in raw_norm:
        raw_tokens.update(line.split())

    for lineno, tline in enumerate(transcript, 1):
        t_norm = _norm(tline)
        if not t_norm:
            continue
        # 1) exact-ish line present?
        if any(t_norm == r for r in raw_norm):
            continue
        # 2) every token of the transcribed line appears somewhere in raw text
        #    (handles OCR reordering / wrapping differences).
        missing = [tok for tok in t_norm.split() if tok not in raw_tokens]
        if not missing:
            continue
        # 3) fuzzy: closest raw line
        best = difflib.get_close_matches(t_norm, raw_norm, n=1, cutoff=0.6)
        hint = f"closest raw: {best[0]!r}" if best else "no close match"
        mismatches.append(
            f"{sid} transcript line {lineno}: {tline!r} "
            f"(missing tokens: {missing}; {hint})"
        )

    info.append(
        f"{sid}: compared {len(transcript)} transcribed lines "
        f"against text extracted via {', '.join(method) or 'none'}"
    )
    return mismatches, info


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", help="only check this source_id")
    parser.add_argument("--no-ocr", action="store_true", help="skip OCR fallback")
    parser.add_argument("--report", help="also write output to this file")
    args = parser.parse_args()

    sources, chunks = _load_corpus()
    lines: list[str] = []
    n_mismatch = 0

    for source in sources:
        sid = source["source_id"]
        if args.source and sid != args.source:
            continue
        lines.append(f"\n=== {sid} ({source['extraction']}) ===")
        if source["extraction"] == "html_text":
            errs = check_html(source, chunks)
            if errs:
                n_mismatch += len(errs)
                lines.append("MISMATCH")
                lines.extend(f"  - {e}" for e in errs)
            else:
                lines.append(
                    f"  OK: all {len(chunks[sid])} chunks' lines "
                    "are verbatim in the saved HTML."
                )
        elif source["extraction"] == "manual_transcription":
            mismatches, info = check_manual(source, chunks, not args.no_ocr)
            lines.extend(f"  {i}" for i in info)
            if mismatches:
                n_mismatch += len(mismatches)
                lines.append(
                    "  NEEDS HUMAN CHECK (auto-diff found these lines suspect; "
                    "confirm against the image/PDF):"
                )
                lines.extend(f"    {m}" for m in mismatches)
            else:
                lines.append(
                    "  No auto-detected mismatch, but the human review is still "
                    "required (OCR may miss errors)."
                )
        else:
            lines.append(f"  unknown extraction {source.extraction!r}")

    out = "\n".join(lines)
    print(out)
    if args.report:
        Path(args.report).write_text(out + "\n", encoding="utf-8")
        print(f"\nReport written to {args.report}")

    if n_mismatch:
        print(f"\n{n_mismatch} potential mismatch(es) found.")
        return 1
    print("\nNo transcription mismatches found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

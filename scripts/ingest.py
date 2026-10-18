"""Rebuild the read-only Chroma store from corpus/ (M1).

    python scripts/ingest.py                     # validate + build
    python scripts/ingest.py --check             # validate only, no embedding
    python scripts/ingest.py --require-reviewed  # refuse unless every source
                                                 # and chunk is human-reviewed

Checks run before anything is written:
  * every chunk's line range exists and is non-empty, ids are unique;
  * tiers, streams and caveat tags are known (manifest.yaml / policy.yaml);
  * hazardous / no-standard chunks list the items they apply to;
  * every raw snapshot file listed in the manifest exists;
  * for `html_text` sources, every chunk line is copied verbatim from the
    saved HTML (so excerpts are provably official text).
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from htmltext import html_lines, normalise_line  # noqa: E402

from backend.app.config import load_settings  # noqa: E402
from backend.app.policy import get_policy  # noqa: E402
from backend.app.retrieval.corpus import (  # noqa: E402
    CorpusError,
    chunk_to_metadata,
    embedding_text,
    load_all_chunks,
)


def validate(require_reviewed: bool) -> tuple[object, list]:
    manifest, chunks = load_all_chunks()
    policy = get_policy()
    errors: list[str] = []
    warnings: list[str] = []

    by_source: dict[str, list] = {}
    for ac in chunks:
        by_source.setdefault(ac.chunk.source_id, []).append(ac)
        unknown = [t for t in ac.chunk.caveat_tags if t not in policy.caveats]
        if unknown:
            errors.append(f"{ac.chunk.chunk_id}: caveat tag(s) {unknown} have no text in policy.yaml")

    for source in manifest.sources:
        for f in source.raw_files:
            if not f.exists():
                errors.append(f"{source.source_id}: raw snapshot missing: {f}")
        if source.source_id not in by_source:
            errors.append(f"{source.source_id}: no chunks")
            continue
        if source.extraction == "html_text":
            html = next((f for f in source.raw_files if f.suffix == ".html"), None)
            if html is None or not html.exists():
                errors.append(f"{source.source_id}: html_text source without an .html snapshot")
                continue
            page = " " + " ".join(html_lines(html)) + " "
            for ac in by_source[source.source_id]:
                for line in ac.chunk.text.splitlines():
                    if normalise_line(line) not in page:
                        errors.append(f"{ac.chunk.chunk_id}: line not found in snapshot: {line!r}")
        elif source.extraction == "manual_transcription":
            warnings.append(
                f"{source.source_id}: manual transcription ({len(by_source[source.source_id])} chunks) "
                "- must be checked against the raw file before review"
            )
        else:
            errors.append(f"{source.source_id}: unknown extraction {source.extraction!r}")

        if require_reviewed:
            if source.review_status != "reviewed":
                errors.append(f"{source.source_id}: source review status is {source.review_status!r}")
            for ac in by_source[source.source_id]:
                if ac.review_status != "reviewed":
                    errors.append(f"{ac.chunk.chunk_id}: chunk review status is {ac.review_status!r}")

    for w in warnings:
        print(f"WARNING {w}")
    if errors:
        for e in errors:
            print(f"ERROR   {e}")
        raise SystemExit(f"Corpus validation failed with {len(errors)} error(s).")
    return manifest, chunks


def build(manifest, chunks) -> None:  # type: ignore[no-untyped-def]
    import chromadb

    from backend.app.retrieval.store import HFEmbedder

    settings = load_settings()
    path = settings.chroma_path
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)

    embedder = HFEmbedder(settings.embed_model)
    texts = [embedding_text(ac.chunk) for ac in chunks]
    print(f"Embedding {len(texts)} chunks with {settings.embed_model} ...")
    vectors = embedder.embed_documents(texts)

    client = chromadb.PersistentClient(path=str(path))
    collection = client.create_collection(
        name=settings.chroma_collection,
        configuration={"hnsw": {"space": "cosine"}},
        metadata={"corpus_version": manifest.corpus_version, "embed_model": settings.embed_model},
        embedding_function=None,
    )
    collection.add(
        ids=[ac.chunk.chunk_id for ac in chunks],
        documents=[ac.chunk.text for ac in chunks],
        metadatas=[chunk_to_metadata(ac.chunk) for ac in chunks],
        embeddings=vectors,
    )
    print(f"Wrote {collection.count()} chunks to {path} (corpus {manifest.corpus_version}).")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="validate only")
    parser.add_argument("--require-reviewed", action="store_true", help="fail on any draft source/chunk")
    args = parser.parse_args()
    try:
        manifest, chunks = validate(args.require_reviewed)
    except CorpusError as exc:
        raise SystemExit(f"Corpus error: {exc}") from exc

    tiers: dict[str, int] = {}
    for ac in chunks:
        tiers[ac.chunk.rule_tier] = tiers.get(ac.chunk.rule_tier, 0) + 1
    print(f"Corpus OK: {len(chunks)} chunks from {len(manifest.sources)} sources; tiers {tiers}")
    if not args.check:
        build(manifest, chunks)


if __name__ == "__main__":
    main()

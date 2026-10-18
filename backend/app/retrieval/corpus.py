"""Load and validate the corpus files (manifest, normalised text, chunk tags).

Used by scripts/ingest.py to build Chroma, and by the server to read the
stream vocabulary. At runtime chunk text is read back from Chroma, never from
these files, so the store is the single source of excerpts (R9).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..config import REPO_ROOT
from ..schemas import Chunk

CORPUS_DIR = REPO_ROOT / "corpus"
VALID_TIERS = ("general_recyclable", "hazardous_unified", "no_unified_standard", "info")
STRICT_TIERS = ("hazardous_unified", "no_unified_standard")


class CorpusError(ValueError):
    pass


@dataclass(frozen=True)
class SourceInfo:
    source_id: str
    title: str
    url: str
    retrieved_at: str
    extraction: str
    raw_files: tuple[Path, ...]
    review_status: str


@dataclass(frozen=True)
class Manifest:
    corpus_version: str
    streams: tuple[str, ...]
    bin_vocabulary: tuple[str, ...]
    sources: tuple[SourceInfo, ...]

    def canonical_stream(self, name: str | None) -> str | None:
        if name is None:
            return None
        for s in self.streams:
            if s.casefold() == name.strip().casefold():
                return s
        raise CorpusError(f"unknown stream {name!r}; add it to manifest.yaml streams")


def load_manifest(corpus_dir: Path = CORPUS_DIR) -> Manifest:
    raw = yaml.safe_load((corpus_dir / "manifest.yaml").read_text(encoding="utf-8"))
    sources = tuple(
        SourceInfo(
            source_id=s["source_id"],
            title=s["title"],
            url=s["url"],
            retrieved_at=str(s["retrieved_at"]),
            extraction=s["extraction"],
            raw_files=tuple(corpus_dir / f for f in s["raw_files"]),
            review_status=(s.get("review") or {}).get("status", "draft"),
        )
        for s in raw["sources"]
    )
    return Manifest(
        corpus_version=str(raw["corpus_version"]),
        streams=tuple(raw["streams"]),
        bin_vocabulary=tuple(raw.get("bin_vocabulary") or raw["streams"]),
        sources=sources,
    )


@dataclass(frozen=True)
class AnnotatedChunk:
    chunk: Chunk
    review_status: str


def load_source_chunks(source: SourceInfo, manifest: Manifest, corpus_dir: Path = CORPUS_DIR) -> list[AnnotatedChunk]:
    txt_path = corpus_dir / "chunks" / f"{source.source_id}.txt"
    tag_path = corpus_dir / "chunks" / f"{source.source_id}.yaml"
    lines = txt_path.read_text(encoding="utf-8").splitlines()
    tags: dict[str, Any] = yaml.safe_load(tag_path.read_text(encoding="utf-8"))
    if tags.get("source_id") != source.source_id:
        raise CorpusError(f"{tag_path.name}: source_id does not match the manifest")
    default_status = tags.get("review_status", "draft")

    out: list[AnnotatedChunk] = []
    for entry in tags["chunks"]:
        cid = entry["id"]
        start, end = entry["lines"]
        if not (1 <= start <= end <= len(lines)):
            raise CorpusError(f"{cid}: lines {start}-{end} outside {txt_path.name} (1-{len(lines)})")
        body = lines[start - 1 : end]
        if any(not line.strip() for line in body):
            raise CorpusError(f"{cid}: empty line inside its range")
        tier = entry["tier"]
        if tier not in VALID_TIERS:
            raise CorpusError(f"{cid}: unknown tier {tier!r}")
        applies_to = tuple(str(t) for t in entry.get("applies_to") or ())
        if tier in STRICT_TIERS and not applies_to:
            raise CorpusError(f"{cid}: {tier} chunks need applies_to terms")
        chunk = Chunk(
            chunk_id=cid,
            source_id=source.source_id,
            doc_title=source.title,
            url=source.url,
            retrieved_at=source.retrieved_at,
            section=entry["section"],
            line_start=start,
            line_end=end,
            rule_tier=tier,
            stream=manifest.canonical_stream(entry.get("stream")),
            caveat_tags=tuple(entry.get("caveats") or ()),
            applies_to=applies_to,
            text="\n".join(body),
        )
        out.append(AnnotatedChunk(chunk=chunk, review_status=entry.get("review_status", default_status)))
    return out


def load_all_chunks(corpus_dir: Path = CORPUS_DIR) -> tuple[Manifest, list[AnnotatedChunk]]:
    manifest = load_manifest(corpus_dir)
    chunks: list[AnnotatedChunk] = []
    seen: set[str] = set()
    for source in manifest.sources:
        for ac in load_source_chunks(source, manifest, corpus_dir):
            if ac.chunk.chunk_id in seen:
                raise CorpusError(f"duplicate chunk id {ac.chunk.chunk_id}")
            seen.add(ac.chunk.chunk_id)
            chunks.append(ac)
    return manifest, chunks


def embedding_text(chunk: Chunk) -> str:
    """Text that is embedded for retrieval (the excerpt itself stays verbatim).

    DO/DON'T list items are embedded as plain item text, other chunks as text
    plus section. Chosen on the dev split (eval/reports/tau_calibration.md):
    with bge-small, extra category words made short items match each other
    instead of the user's item.
    """
    if "DON'T" in chunk.section or "DOs" in chunk.section:
        return chunk.text
    return f"{chunk.text} — {chunk.section}"


# Chroma metadata values must be scalars, so tuples are stored as strings.
_SEP = "|"


def chunk_to_metadata(chunk: Chunk) -> dict[str, str | int]:
    return {
        "source_id": chunk.source_id,
        "doc_title": chunk.doc_title,
        "url": chunk.url,
        "retrieved_at": chunk.retrieved_at,
        "section": chunk.section,
        "line_start": chunk.line_start,
        "line_end": chunk.line_end,
        "rule_tier": chunk.rule_tier,
        "stream": chunk.stream or "",
        "caveat_tags": _SEP.join(chunk.caveat_tags),
        "applies_to": _SEP.join(chunk.applies_to),
    }


def chunk_from_record(chunk_id: str, document: str, meta: dict[str, Any]) -> Chunk:
    def split(value: Any) -> tuple[str, ...]:
        return tuple(v for v in str(value or "").split(_SEP) if v)

    return Chunk(
        chunk_id=chunk_id,
        source_id=str(meta["source_id"]),
        doc_title=str(meta["doc_title"]),
        url=str(meta["url"]),
        retrieved_at=str(meta["retrieved_at"]),
        section=str(meta["section"]),
        line_start=int(meta["line_start"]),
        line_end=int(meta["line_end"]),
        rule_tier=meta["rule_tier"],
        stream=str(meta["stream"]) or None,
        caveat_tags=split(meta.get("caveat_tags")),
        applies_to=split(meta.get("applies_to")),
        text=document,
    )

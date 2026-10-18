"""Calibrate the retrieval threshold tau on the DEV split only (FR-3).

    python -m eval.calibrate_tau --split dev

Positives are dev text cases tagged `calibration_positive` or
`general_recyclable` (the corpus answers them). Negatives are cases tagged
`calibration_negative` (the corpus does not). For each, the top-1 cosine score
of the message is computed; tau is chosen to maximise balanced accuracy, and
placed in the middle of the gap when several values tie. Writes
eval/reports/tau_calibration.md. Never run this on the test split.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.config import load_settings  # noqa: E402
from eval.run_eval import REPORTS_DIR, load_cases  # noqa: E402


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--split", choices=["dev"], default="dev")
    args = parser.parse_args()

    from backend.app.retrieval.store import ChunkStore, HFEmbedder, Retriever

    settings = load_settings()
    store = ChunkStore(settings)
    retriever = Retriever(store, HFEmbedder(settings.embed_model))

    rows: list[tuple[str, str, float, str, str]] = []
    for case in load_cases(args.split, "text"):
        tags = set(case.get("tags", []))
        if "calibration_negative" in tags:
            label = "neg"
        elif tags & {"calibration_positive", "general_recyclable"}:
            label = "pos"
        else:
            continue
        hits = retriever.search(case["input"], settings.retrieve_top_k)
        top = hits[0] if hits else None
        rows.append((case["id"], label, top.score if top else 0.0, top.chunk.chunk_id if top else "", case["input"]))

    pos = sorted(s for _, lab, s, _, _ in rows if lab == "pos")
    neg = sorted(s for _, lab, s, _, _ in rows if lab == "neg")
    if not pos or not neg:
        raise SystemExit("Need both positive and negative calibration cases in the dev split.")

    candidates = sorted({round(s, 4) for _, _, s, _, _ in rows})
    best: list[tuple[float, float]] = []
    for i, t in enumerate(candidates):
        tpr = sum(s >= t for s in pos) / len(pos)
        tnr = sum(s < t for s in neg) / len(neg)
        bal = (tpr + tnr) / 2
        best.append((bal, t))
    top_bal = max(b for b, _ in best)
    tied = sorted(t for b, t in best if b == top_bal)
    # Midpoint between the lowest tied threshold and the highest negative below it.
    t_low = tied[0]
    below = [s for s in neg if s < t_low]
    tau = round((t_low + max(below)) / 2, 3) if below else t_low

    tpr = sum(s >= tau for s in pos) / len(pos)
    tnr = sum(s < tau for s in neg) / len(neg)
    lines = [
        "# Retrieval threshold calibration (dev split)",
        "",
        f"- Run: {dt.datetime.now():%Y-%m-%d %H:%M}",
        f"- Embedding model: `{settings.embed_model}`, corpus `{store.corpus_version}`",
        f"- Positives: {len(pos)} (min {pos[0]:.3f}, median {pos[len(pos) // 2]:.3f}); negatives: {len(neg)} (max {neg[-1]:.3f})",
        f"- **Recommended RETRIEVE_TAU = {tau}** (balanced accuracy {top_bal:.2f}; at tau: TPR {tpr:.2f}, TNR {tnr:.2f})",
        "",
        "Scores overlap, so tau is a coarse filter. Questions the corpus does not cover but",
        "that score above tau are caught by the answer model's `answers_question=false`",
        "(-> LOW_RETRIEVAL_MATCH) and off-topic ones by the intent call.",
        "",
        "| case | label | top-1 score | top-1 chunk | question |",
        "|---|---|---|---|---|",
    ]
    for cid, lab, s, chunk, q in sorted(rows, key=lambda r: r[2], reverse=True):
        lines.append(f"| {cid} | {lab} | {s:.3f} | {chunk} | {q} |")
    out = REPORTS_DIR / "tau_calibration.md"
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:6]))
    print(f"Report: {out.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()

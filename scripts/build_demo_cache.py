"""Pre-generate demo-cache answers for the sample questions (FR-10).

    python scripts/build_demo_cache.py

Runs the live pipeline (needs an LLM API key) on every sample question in
backend/app/policy/policy.yaml and writes backend/app/demo_cache.json with
"reviewed": false. A team member must read each entry and set
"reviewed": true before the server will ever serve it. SERVICE_UNAVAILABLE
results are not cached. Images are never cached (R8).
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from backend.app.config import load_settings  # noqa: E402
from backend.app.services import build_deps  # noqa: E402
from backend.app.workflow import Pipeline  # noqa: E402


async def build() -> None:
    settings = load_settings(demo_cache="off")
    if not settings.llm_enabled:
        print("WARNING: no LLM configured; answer-path samples will be skipped.")
    deps, _ = build_deps(settings)
    pipeline = Pipeline(deps)
    entries = []
    for question in deps.policy.samples:
        result = await pipeline.run(question)
        r = result.response
        if r.reason_code == "SERVICE_UNAVAILABLE":
            print(f"skip  {question!r}: service unavailable")
            continue
        entries.append({"question": question, "reviewed": False, "response": r.model_dump(mode="json")})
        print(f"ok    {question!r}: {r.action} / {r.reason_code}")
    out = settings.demo_cache_path
    out.write_text(json.dumps({"entries": entries}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(entries)} entries to {out}. Review each one and set \"reviewed\": true.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    asyncio.run(build())

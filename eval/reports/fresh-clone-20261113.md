# Fresh-clone reproduction check

- **Date:** 2026-11-13
- **Environment:** Windows 11, Python 3.13, Node.js 22
- **Repository:** https://github.com/Ral151/AILT9019-G07 (commit `58d7128`)

## Goal

Verify that a clean checkout of the repository can be built and run end-to-end
following the README — with no secrets committed, and all git-ignored artefacts
(frontend build, vector store) regenerated from source.

## Steps and results

**1. Fresh clone** — `git clone https://github.com/Ral151/AILT9019-G07.git`
- Pass. `.env` is **absent** (no secrets committed); `.env.example` is present.
- `frontend/dist` and `data/chroma` are absent, as expected (both git-ignored).

**2. Frontend build** — `npm --prefix frontend install && npm --prefix frontend run build`
- Pass. `frontend/dist/index.html` produced (27 modules transformed).

**3. Vector store rebuild** — `python scripts/ingest.py --require-reviewed`
- Pass. Corpus validated: **131 chunks from 6 sources**, tiers
  `{general_recyclable: 43, info: 77, hazardous_unified: 11}`.
- `data/chroma` rebuilt; `BAAI/bge-small-en-v1.5` weights loaded.

**4. Run** — `flask --app backend.app run`
- `GET /api/health` → `status: ok`, 131 chunks, `text_provider: qwen`,
  `text_provider_reachable: true`.

**5. End-to-end** — `POST /api/ask`

| Question | Observed |
|---|---|
| "Does a Coke bottle go in the metal category?" | `answer`, bin `Plastic`, citation `r101_poster` §Plastic > DOs, lines 31–31 |
| "Where should I dispose of used batteries?" | `defer` (`HAZARDOUS_OFFICIAL_LINKS_ONLY`) |
| "Where do I put an old phone charger?" | `refuse` (`NO_UNIFIED_STANDARD`) |

## Conclusion

A clean clone reproduces the core path — build → ingest → run → cited answer —
with the safety refusals intact.

## Note (known limitation)

Text answers occasionally hit a transient `VALIDATION_FAILED`: the LLM returns
output that fails the JSON-schema check, is retried once, and on a rare repeat
failure the app refuses safely instead of guessing. This is LLM-output variance,
not a pipeline defect.

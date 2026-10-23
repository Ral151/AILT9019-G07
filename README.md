# HKU Recycling Rules Helper

A question-and-answer web app that tells you how to sort waste on the HKU campus, based exclusively on official HKU recycling documents. Every answer comes with an exact citation from the source text.

## Try these questions

- "Can a bubble tea cup go into the smart recycling bin?"
- "Does a Coke bottle go in the metal category?"
- "Where should I dispose of used batteries?" (you get official excerpts and links only)
- "Where do I put an old phone charger?" (you get a polite refusal and where to ask)

## What it will and won't do

- Answers come only from HKU's official recycling documents (the re Campaign
  pages and posters, saved on 18 Oct 2026). Every answer shows the quoted
  source text, its section and lines, and a link.
- If the documents don't clearly cover your item, it says so and points you to
  the re Campaign website, your hall tutor, or CEDARS. It does not guess.
- Batteries and other hazardous items: official excerpts and links only.
- Chargers, small electrical appliances, furniture and other bulky items:
  there's no campus-wide rule, so it won't name a bin.
- **On-site signs and staff always take priority.** Hall rules may vary.
- HKU campus only. No fines or appeals, no disposal applications.

---

## For developers

### Stack

| Layer | Choice |
|---|---|
| Frontend | React 19 + TypeScript (strict) + Tailwind CSS 4, built with Vite 8 |
| Backend | Flask 3 (async views), pydantic v2 schemas |
| Pipeline | LlamaIndex Workflow (`backend/app/workflow/pipeline.py`) |
| Vector DB | ChromaDB `PersistentClient` in `data/chroma/`, built offline, read-only at runtime |
| Embeddings | Local `BAAI/bge-small-en-v1.5` via LlamaIndex HuggingFace |
| Text LLM | Any OpenAI-compatible API. Default: OpenRouter `nvidia/nemotron-3.5-super-vl:free`; alternative: Qwen on Alibaba Cloud Model Studio |

### Run it locally

Prerequisites: Python 3.11+ (tested on 3.13), Node 20+ (tested on 22).

```bash
# 1. Backend dependencies
python -m venv .venv
.venv/Scripts/activate            # Windows (Git Bash: source .venv/Scripts/activate)
# source .venv/bin/activate       # macOS / Linux
pip install -r backend/requirements.txt

# 2. Build the vector store from corpus/ (downloads bge-small once, ~130 MB)
python scripts/ingest.py

# 3. Configuration
cp .env.example .env              # then set OPENROUTER_API_KEY (optional, see below)

# 4. Start the API on http://127.0.0.1:5000
flask --app backend.app run --debug

# 5. In a second terminal: the web app on http://localhost:5173
npm --prefix frontend install
npm --prefix frontend run dev
```

To serve everything from Flask instead, run `npm --prefix frontend run build`
and open http://127.0.0.1:5000.

**Without an API key** the app runs in safe mode. Out-of-scope refusals,
sign-conflict deferrals, hazardous excerpts and unsupported-item refusals all
work, because they are fixed templates. Normal answers return
`SERVICE_UNAVAILABLE` (or a reviewed demo-cache answer) until you set
`OPENROUTER_API_KEY` (or `QWEN_API_KEY`) in `.env` and restart Flask. Check
`GET /api/health`: it shows `text_provider: "openrouter"`, the model, and
whether the provider is reachable.

**Free-model limits.** OpenRouter `:free` models allow 20 requests per minute
and 50 per day (1,000 per day once the account has bought at least $10 of
credit). Each text question uses two LLM calls, so one full dev-split eval
can use up a day's free requests. The eval harness caches LLM outputs, so
re-scoring an unchanged run is free.

### Commands

| Command | Purpose |
|---|---|
| `npm --prefix frontend run dev \| build \| test` | Frontend |
| `flask --app backend.app run --debug` | Backend |
| `python scripts/ingest.py` | Validate `corpus/` and rebuild Chroma (`--check` to validate only, `--require-reviewed` to freeze) |
| `python scripts/check_transcription.py` | Cross-check each source's transcription against its raw file (`--source` to pick one) |
| `python -m eval.run_eval --split dev\|test --report` | Score cases; exits non-zero on any critical failure or failed must-have case |
| `python -m eval.calibrate_tau --split dev` | Re-calibrate `RETRIEVE_TAU` (dev split only) |
| `python scripts/build_demo_cache.py` | Pre-generate demo answers for the sample questions (needs a key; review before use) |
| `pytest backend/tests` | Unit tests (rules, router, validators, schemas, pipeline, API, corpus) |

`eval.run_eval` options: `--modality text|image|all`, `--llm auto|none|mock`
(`mock` checks plumbing only and is never a valid score), `--no-cache`.

### How a question is answered

```
POST /api/ask (multipart: message, optional image)
  1 ValidateInput   size caps; photo re-validated and re-encoded in memory
  2 BoundaryCheck   keyword rules (policy.yaml), then the LLM intent call -> early refuse/defer
  3 Vision          photo -> item name (text-only fallback for now)
  4 Retrieve        Chroma top-5 for the question and each extracted item
  5 Route           deterministic router: hazardous -> unsupported -> low match -> answer
  6 Generate        Qwen writes <= 2 sentences from the selected excerpts (JSON)
  7 Validate        checks; one retry; else VALIDATION_FAILED
  8 Respond         excerpts copied from the store by the server, caveats from chunk tags
```

Safety decisions are code, not LLM judgement. The LLM can only make an outcome
stricter: it can never turn a refusal into an answer.

### Repository layout

```
backend/app/
  routes/      Flask blueprint: /api/ask, /api/health, /api/samples
  schemas/     pydantic models for the API contract and LLM outputs
  workflow/    LlamaIndex Workflow 
  policy/      policy.yaml (scope keywords, templates, caveat texts), rules, router, validators
  providers/   Qwen text LLM (+ mock, + eval cache); vision interface
  prompts/     versioned prompt files (intent_v1, answer_v1)
  retrieval/   corpus loader, Chroma store, query normalisation
backend/tests/ pytest suite (rules, router, validators, pipeline, API, corpus, eval harness)
corpus/
  manifest.yaml  sources, URLs, retrieval dates, stream taxonomy, review status
  raw/           saved snapshots (HTML, poster PDF and images)
  chunks/        <source>.txt (normalised text, stable line numbers) + <source>.yaml (tags)
data/chroma/     built by scripts/ingest.py (git-ignored)
eval/
  cases/{dev,test}/  text.jsonl, image.jsonl 
  run_eval.py, calibrate_tau.py, faithfulness_review.md, reports/
frontend/src/    components, hooks, api, types
scripts/         ingest.py, htmltext.py, check_transcription.py, build_demo_cache.py
transcription_checklist.md  poster transcription line-by-line review checklist
```

### Corpus review

`corpus/manifest.yaml` marks every source `review.status: draft`.

- `html_text` sources (re Facilities, quiz, GreenU): ingest proves every line is
  copied from the saved HTML.
- `manual_transcription` sources (the Recycling 101 posters, which are images):
  a team member must check each line of `corpus/chunks/r101_*.txt` against
  `corpus/raw/`.

Then check each chunk's `tier`, `stream` and `caveats` in the `.yaml`, and set
`review_status: reviewed`. `python scripts/ingest.py --require-reviewed` must
pass before the test set is frozen.

`scripts/check_transcription.py` automates the first pass (it verifies the
`html_text` sources and flags suspect lines in the posters), and
`transcription_checklist.md` is the line-by-line checklist used for the
`manual_transcription` posters. `eval/faithfulness_review.md` records the
answer-path faithfulness sign-off for the test split.

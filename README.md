# HKU Campus Recycling Rules Helper

A question-and-answer web app that tells you how to sort waste on the HKU campus, based **exclusively** on official HKU recycling documents. Every answer comes with an exact citation from the source text.

## Architecture (Real RAG Pipeline)

```
┌─────────────────────────── Offline (one-time) ───────────────────────────┐
│  sources.json  →  collect_docs.py  →  corpus_processor.py  →  corpus.json │
│  (URL config)     (fetch & clean)     (chunk & number)      (encyclopedia)│
└──────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────── Online (per question) ────────────────────────┐
│  user input  →  boundary.py  →  retriever.py  →  generator.py  →  reply  │
│                (rule layer)     (top-1..3)        (cite every fact)       │
└──────────────────────────────────────────────────────────────────────────┘
```

- **boundary.py** — rule layer: off-campus / complaints / no-standard → refuse; sign conflict → defer; batteries → official excerpts only.
- **retriever.py** — TF-IDF retrieval of the top 1–3 relevant paragraphs from the encyclopedia.
- **generator.py** — rewrites the retrieved text only; every fact is cited `[source#paragraph]`. Insufficient basis → refuses. Falls back to `cache.json` or a template builder when no LLM API key is set.

## Project Structure

```
AILT9019/
├── app.py                  # Flask web server (entry point)
├── boundary.py             # Rule layer (refuse / defer / caveat)
├── retriever.py            # TF-IDF retrieval
├── generator.py            # Answer generation with citations
├── collect_docs.py         # Offline: fetch & clean official docs
├── corpus_processor.py     # Offline: chunk & number paragraphs
├── sources.json            # Offline: source URL config
├── hku_recycling_corpus.json  # The encyclopedia (66 entries)
├── cache.json              # Pre-stored demo answers (LLM-unavailable fallback)
├── corpus_raw/             # Cleaned source text (.txt)
├── templates/index.html    # Web interface
├── requirements.txt
├── .env.example            # API key template
└── test_cases.csv          # 45 test cases (30 text + 15 image)
```

## How to Set Up and Run the Core Workflow

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. (Optional) Configure an LLM API key

Copy `.env.example` to `.env` and add your key:

```bash
cp .env.example .env
# then edit .env and set OPENAI_API_KEY=...
```

If no key is provided, the app uses a built-in template-based generator that still works for every question.

### 3. Start the app

```bash
python app.py
```

Open **http://localhost:8000** in your browser.

## How to Check the Result

Try these four standard test cases (the project's acceptance criteria):

| # | Test question | Expected behaviour |
|---|---|---|
| 1 | "Where does plastic go?" | Answer with citation → Plastic recycling bin, cites `recycling_101#7` |
| 2 | "The floor sign says no plastic bottles but you said yes — who do I follow?" | Defer to on-site signage |
| 3 | "Where do I put an old phone charger?" | Refuse → no campus-wide standard, consult hall tutor |
| 4 | "I'm in Causeway Bay — where can I throw this plastic bottle?" | Refuse → HKU campus only |

You can also run the automated check against all 30 text test cases:

```bash
python -c "
import csv
from boundary import classify_question
with open('test_cases.csv') as f:
    rows = [r for r in csv.DictReader(f) if r['input_type']=='text']
p = sum(1 for r in rows if classify_question(r['input_content']).action == (r['expected_safety_action'] if r['expected_safety_action']!='N/A' else 'defer'))
print(f'{p}/{len(rows)} text test cases pass')
"
```

## Safety Notes

- Every answer cites the exact official source paragraph. If the documents don't contain the answer, the app refuses rather than guessing.
- Hazardous waste (batteries, fluorescent tubes, medication): only official guidance links and excerpts — no operational disposal advice.
- On-site signage/staff always take precedence over the system's general rule.

"""
app.py - HKU Campus Recycling Rules Helper - Web Server

Flask application that wires together the full RAG pipeline:
  user question -> boundary.py (rule layer) -> retriever.py (top-1..3)
                 -> generator.py (cited answer) -> JSON response

Endpoints:
  GET  /            -> the chat web page (templates/index.html)
  POST /api/ask     -> { "question": "..." } -> full pipeline result as JSON
  GET  /api/health  -> health check

Run:
  python app.py
then open http://localhost:8000
"""

import json
import os
import sys
from flask import Flask, request, jsonify, render_template

# Ensure project root is on the path so the modules import cleanly.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from boundary import classify_question
from retriever import Retriever
from generator import Generator


# Load .env manually (avoid requiring python-dotenv).
def load_dotenv(path=".env"):
    env_path = os.path.join(BASE_DIR, path)
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


load_dotenv()

app = Flask(__name__, template_folder=os.path.join(BASE_DIR, "templates"))

# Initialise pipeline components once at startup.
retriever = Retriever()
generator = Generator()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "corpus_entries": retriever.entry_count,
        "llm_available": bool(generator.api_key),
    })


@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "Question is required."}), 400

    # Step 1: boundary / rule layer
    decision = classify_question(question)

    # Step 2: retrieval (only if we might answer)
    retrieved = []
    if decision.action in ("answer", "defer", "answer_with_caveat"):
        retrieved = retriever.retrieve(question, top_k=3)

    # Step 3: generation
    result = generator.generate(question, retrieved, decision)

    response = {
        "question": question,
        "action": result["action"],
        "answer": result["answer"],
        "citations": result["citations"],
        "reminder": result.get("reminder", ""),
        "boundary_reason": decision.reason,
        "used_cache": result["used_cache"],
        "used_llm": result["used_llm"],
    }
    return jsonify(response)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"HKU Recycling Helper starting on http://localhost:{port}")
    print(f"  Corpus entries: {retriever.entry_count}")
    print(f"  LLM API key configured: {bool(generator.api_key)}")
    app.run(host="0.0.0.0", port=port, debug=False)

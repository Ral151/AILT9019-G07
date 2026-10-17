"""
retriever.py - Online Q&A Pipeline Step 2: Retrieval

Loads the encyclopedia (hku_recycling_corpus.json) and, given a user question,
returns the top 1-3 most relevant paragraphs using a TF-IDF + cosine
similarity score (implemented with the Python standard library only, so no
external dependencies are required).

A small tag-boosting step is applied: if the question mentions a material tag
(e.g. "plastic", "paper", "metal", "glass", "battery"), entries carrying that
tag receive a score boost.

Usage:
    from retriever import Retriever
    r = Retriever()
    results = r.retrieve("Where does plastic go?", top_k=3)
    # results: list of dict {entry, score}
"""

import json
import math
import os
import re
from collections import Counter
from typing import List, Dict, Any


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORPUS_FILE = os.path.join(BASE_DIR, "hku_recycling_corpus.json")

# Common English stop words for the recycling domain.
STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "of", "to", "in",
    "on", "at", "for", "with", "by", "from", "is", "are", "was", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "can", "this",
    "that", "these", "those", "it", "its", "i", "you", "we", "they",
    "he", "she", "what", "which", "who", "how", "where", "when", "why",
    "does", "do", "so", "not", "no", "yes", "as", "into", "about",
    "up", "down", "out", "off", "over", "under", "than", "too", "very",
    "just", "also", "only", "other", "some", "any", "all", "each",
    "my", "your", "our", "their", "me", "him", "her", "us", "them",
    "go", "goes", "going", "went", "put", "puts", "throw", "throwing",
    "dispose", "disposal", "disposing", "recycle", "recycling", "recycled",
    "bin", "bins", "category", "categories", "kind", "type", "types",
    "item", "items", "thing", "things", "waste", "sort", "sorting",
    "use", "used", "using", "way", "ways", "should", "must",
}


def tokenize(text: str) -> List[str]:
    """Lowercase, split on non-alphanumeric, drop stop words and short tokens."""
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    return [t for t in tokens if t not in STOP_WORDS and len(t) > 1]


class Retriever:
    def __init__(self, corpus_path: str = CORPUS_FILE):
        with open(corpus_path, "r", encoding="utf-8") as f:
            enc = json.load(f)
        self.entries: List[Dict[str, Any]] = enc["entries"]
        self.entry_count = enc.get("entry_count", len(self.entries))

        # Pre-compute token lists and document frequencies.
        self._doc_tokens: List[List[str]] = []
        self._doc_tf: List[Counter] = []
        df: Counter = Counter()
        for e in self.entries:
            toks = tokenize(e["text"])
            self._doc_tokens.append(toks)
            tf = Counter(toks)
            self._doc_tf.append(tf)
            for term in set(toks):
                df[term] += 1
        self._df = df
        self._N = len(self.entries)
        # Pre-compute IDF and each document's TF-IDF vector norm.
        self._idf: Dict[str, float] = {
            term: math.log((self._N + 1) / (df_t + 1)) + 1.0
            for term, df_t in df.items()
        }
        self._doc_norms: List[float] = []
        for tf in self._doc_tf:
            norm = 0.0
            for term, count in tf.items():
                idf = self._idf.get(term, 0.0)
                tfidf = count * idf
                norm += tfidf * tfidf
            self._doc_norms.append(math.sqrt(norm) if norm > 0 else 1.0)

    # ------------------------------------------------------------------
    def retrieve(self, question: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Return the top_k most relevant entries for the question.

        Each item is a dict: {"entry": {...}, "score": float}.
        """
        q_tokens = tokenize(question)
        if not q_tokens:
            return []

        q_tf = Counter(q_tokens)
        # Query TF-IDF vector.
        q_vec: Dict[str, float] = {}
        q_norm = 0.0
        for term, count in q_tf.items():
            idf = self._idf.get(term, 0.0)
            if idf <= 0:
                continue
            val = count * idf
            q_vec[term] = val
            q_norm += val * val
        q_norm = math.sqrt(q_norm) if q_norm > 0 else 1.0

        scores: List[tuple] = []
        for i, entry in enumerate(self.entries):
            if not q_vec:
                continue
            dot = 0.0
            for term, q_val in q_vec.items():
                if term in self._doc_tf[i]:
                    idf = self._idf[term]
                    d_val = self._doc_tf[i][term] * idf
                    dot += q_val * d_val
            cosine = dot / (q_norm * self._doc_norms[i])

            # Tag boost: if a query token matches an entry tag, add a bonus.
            tag_boost = 0.0
            q_set = set(q_tokens)
            for tag in entry.get("tags", []):
                if tag in q_set:
                    tag_boost += 0.15

            # Contamination boost: if the question mentions
            # greasy/contaminated/dirty and the entry mentions general refuse
            # or "cannot be recycled", boost that entry significantly.
            contam_boost = 0.0
            q_has_contam = any(t in q_set for t in ("greasy", "grease", "contaminated", "dirty", "residue"))
            if q_has_contam:
                etext = entry["text"].lower()
                if "general refuse" in etext or "cannot be recycled" in etext or "not be recycled" in etext:
                    contam_boost += 0.3

            # Specificity adjustment: generic list entries (short paragraphs
            # that just enumerate recyclable categories) are deprioritised in
            # favour of longer, descriptive paragraphs that actually explain
            # sorting rules.
            text_len = len(entry["text"])
            list_penalty = 0.0
            if text_len < 160 and "accept" in entry["text"].lower() and "recyclable" in entry["text"].lower():
                list_penalty = 0.15
            length_boost = min(0.1, text_len / 4000)  # up to +0.1 for long entries

            # Title/source soft boost (small).
            total = cosine + tag_boost + contam_boost + length_boost - list_penalty
            scores.append((total, i))

        scores.sort(key=lambda x: x[0], reverse=True)
        top = scores[:top_k]
        # Filter out zero-score results (no overlap at all).
        results = []
        for score, idx in top:
            if score <= 0:
                continue
            results.append({"entry": self.entries[idx], "score": round(score, 4)})
        return results


def main():
    r = Retriever()
    print(f"Loaded {r.entry_count} encyclopedia entries.\n")
    questions = [
        "Where does plastic go at HKU?",
        "Which bin for aluminium cans?",
        "How to recycle glass bottles?",
        "Where can I recycle batteries?",
        "How many GreenU points for paper?",
    ]
    for q in questions:
        res = r.retrieve(q, top_k=2)
        print(f"Q: {q}")
        for item in res:
            e = item["entry"]
            print(f"   [{item['score']}] {e['id']} :: {e['text'][:90]}...")
        print()


if __name__ == "__main__":
    main()

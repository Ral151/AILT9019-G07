"""
generator.py - Online Q&A Pipeline Step 3: Answer Generation

Takes the retrieved encyclopedia paragraphs and produces a final answer.
Every factual claim MUST be cited back to its source paragraph
(e.g. [recycling_101#7]). If the retrieved context does not contain enough
basis to answer, the generator refuses (insufficient basis).

Two execution modes:
  1. LLM mode  - if an API key is configured (OPENAI_API_KEY or
                 DEEPSEEK_API_KEY), the generator calls an OpenAI-compatible
                 chat endpoint with a strict "rewrite-only-and-cite" prompt.
  2. Template mode - when no API key is available (or the LLM call fails),
                 a deterministic template builder extracts the bin category
                 and key facts from the top retrieved paragraph(s) and
                 assembles a cited answer. This is the always-available
                 fallback so the demo never breaks.

Additionally, cache.json stores pre-written answers for known demo
questions; if an exact (normalised) match is found, it is returned directly
(this is the "LLM API unavailable -> read cache.json" fallback from the
architecture diagram).

Usage:
    from generator import Generator
    g = Generator()
    answer = g.generate(question, retrieved_entries, boundary_decision)
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

from boundary import BoundaryDecision


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CORPUS_FILE = os.path.join(BASE_DIR, "hku_recycling_corpus.json")
CACHE_FILE = os.path.join(BASE_DIR, "cache.json")

# Map common material keywords to a friendly bin category label.
BIN_CATEGORY_MAP = {
    "plastic": "Plastic recycling bin",
    "paper": "Paper recycling bin",
    "metal": "Metal recycling bin",
    "glass": "Glass recycling point (re Kiosk or designated glass bin)",
    "tetra pak": "Tetra Pak recycling (re Kiosk)",
    "battery": "Rechargeable battery collection (re Kiosk only)",
}

MATERIAL_KEYWORDS = {
    "plastic": ["plastic", "pet", "polythene", "foam", "polystyrene", "eps"],
    "paper": ["paper", "newspaper", "cardboard", "carton", "magazine", "textbook", "a4"],
    "metal": ["metal", "aluminium", "aluminum", "tin", "tin can", "aluminium can", "aluminum can", "drink can", "soda can", "cans"],
    "glass": ["glass", "wine bottle", "jam jar"],
    "tetra pak": ["tetra pak", "milk carton", "beverage carton", "juice box"],
    "battery": ["battery", "batteries", "rechargeable"],
}

NO_ANSWER_REFUSAL = (
    "I could not find a sufficiently reliable answer in the official HKU "
    "recycling documents for your question. To avoid giving incorrect "
    "information, I will not guess. Please consult the on-site signage or "
    "your hall tutor for clarification."
)


def normalise_question(q: str) -> str:
    q = q.lower().strip()
    q = re.sub(r"[^a-z0-9\s]", "", q)
    q = re.sub(r"\s+", " ", q)
    return q


def _keyword_in(text: str, keyword: str) -> bool:
    """Match a keyword using word boundaries for single words, substring for phrases."""
    lower = text.lower()
    if " " in keyword or "-" in keyword:
        return keyword in lower
    return bool(re.search(r"\b" + re.escape(keyword) + r"\b", lower))


def detect_material(question: str, entries: List[Dict[str, Any]]) -> Optional[str]:
    """Detect the dominant material. Question text takes priority over retrieved context."""
    q_lower = question.lower()
    # First, try to detect from the question alone.
    for material, kws in MATERIAL_KEYWORDS.items():
        if any(_keyword_in(q_lower, kw) for kw in kws):
            return material
    # Fallback: check only the top retrieved entry (not all entries, to avoid
    # picking up unrelated material mentions from secondary results).
    if entries:
        ctx_lower = entries[0]["entry"]["text"].lower()
        for material, kws in MATERIAL_KEYWORDS.items():
            if any(_keyword_in(ctx_lower, kw) for kw in kws):
                return material
    return None


def citation(entry: Dict[str, Any]) -> str:
    """Return a short citation label: [source#paragraph]."""
    return f"[{entry['id']}]"


def source_label(entry: Dict[str, Any]) -> str:
    return f"{entry['source_title']} (para. {entry['paragraph']})"


class Generator:
    def __init__(self, corpus_path: str = CORPUS_FILE, cache_path: str = CACHE_FILE):
        self.corpus_path = corpus_path
        self.cache_path = cache_path
        self._cache: Dict[str, Dict[str, Any]] = self._load_cache()
        # API configuration from environment.
        self.api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
        self.api_base = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
        self.model = os.environ.get("LLM_MODEL", "gpt-4o-mini")

    # ------------------------------------------------------------------
    def _load_cache(self) -> Dict[str, Dict[str, Any]]:
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    # ------------------------------------------------------------------
    def generate(
        self,
        question: str,
        retrieved: List[Dict[str, Any]],
        decision: BoundaryDecision,
    ) -> Dict[str, Any]:
        """Produce the final answer dict.

        Returns:
            {
              "answer": str,
              "citations": [{"id", "source_title", "paragraph", "url", "excerpt"}],
              "action": str,
              "reminder": str,
              "used_cache": bool,
              "used_llm": bool,
            }
        """
        # --- Refuse / defer / caveat handled by boundary ---
        if decision.action == "refuse":
            return {
                "answer": decision.refusal_message,
                "citations": [],
                "action": "refuse",
                "reminder": "",
                "used_cache": False,
                "used_llm": False,
            }

        if decision.action == "defer":
            # Still try to give the general rule from retrieval.
            general = self._build_general_rule(question, retrieved)
            answer = decision.defer_message
            if general:
                answer += "\n\nGeneral campus rule: " + general
            return {
                "answer": answer,
                "citations": self._collect_citations(retrieved),
                "action": "defer",
                "reminder": "On-site signage/staff instructions take precedence over the general rule.",
                "used_cache": False,
                "used_llm": False,
            }

        if decision.action == "answer_with_caveat":
            if decision.hazardous:
                # Hazardous waste: only official excerpts, no operational advice.
                answer = decision.caveat_message
                excerpts = self._build_hazardous_excerpts(retrieved)
                if excerpts:
                    answer += "\n\nOfficial source excerpt(s):\n" + excerpts
                return {
                    "answer": answer,
                    "citations": self._collect_citations(retrieved),
                    "action": "answer_with_caveat",
                    "reminder": "For hazardous waste, always follow the official designated collection procedures. Do not dispose of in general recycling or refuse bins.",
                    "used_cache": False,
                    "used_llm": False,
                }
            else:
                # Regular caveat (location, cleaning, contamination, hall rules):
                # give a normal cited answer plus a caveat reminder.
                if not retrieved:
                    return {
                        "answer": NO_ANSWER_REFUSAL,
                        "citations": [],
                        "action": "insufficient_basis",
                        "reminder": "",
                        "used_cache": False,
                        "used_llm": False,
                    }
                answer = self._build_template_answer(question, retrieved)
                reminder = self._build_caveat_reminder(question, retrieved)
                return {
                    "answer": answer,
                    "citations": self._collect_citations(retrieved),
                    "action": "answer_with_caveat",
                    "reminder": reminder,
                    "used_cache": False,
                    "used_llm": False,
                }

        # --- Normal answer path ---
        if not retrieved:
            return {
                "answer": NO_ANSWER_REFUSAL,
                "citations": [],
                "action": "insufficient_basis",
                "reminder": "",
                "used_cache": False,
                "used_llm": False,
            }

        # 1) Try exact cache match.
        norm_q = normalise_question(question)
        if norm_q in self._cache:
            cached = self._cache[norm_q]
            return {
                "answer": cached["answer"],
                "citations": cached.get("citations", []),
                "action": "answer",
                "reminder": cached.get("reminder", ""),
                "used_cache": True,
                "used_llm": False,
            }

        # 2) Try LLM.
        if self.api_key:
            llm_answer = self._generate_llm(question, retrieved)
            if llm_answer:
                return {
                    "answer": llm_answer,
                    "citations": self._collect_citations(retrieved),
                    "action": "answer",
                    "reminder": "",
                    "used_cache": False,
                    "used_llm": True,
                }

        # 3) Template-based fallback (always works).
        answer = self._build_template_answer(question, retrieved)
        return {
            "answer": answer,
            "citations": self._collect_citations(retrieved),
            "action": "answer",
            "reminder": "",
            "used_cache": False,
            "used_llm": False,
        }

    # ------------------------------------------------------------------
    def _build_template_answer(self, question: str, retrieved: List[Dict[str, Any]]) -> str:
        """Deterministic answer builder that rewrites retrieved text with citations."""
        material = detect_material(question, retrieved)
        lower_q = question.lower()
        contaminated = any(k in lower_q for k in
                           ["greasy", "grease", "contaminated", "food residue", "food-contaminated", "dirty"])

        top = retrieved[0]["entry"]
        top_text = top["text"]

        # First sentence of the top paragraph as the core statement.
        first_sent = self._first_sentence(top_text)

        parts = []
        parts.append(f"Based on the official HKU recycling documents, here is the answer:")

        if contaminated:
            parts.append(f"\nBin category: General refuse (the item is contaminated and cannot be recycled)")
        elif material and material in BIN_CATEGORY_MAP:
            parts.append(f"\nBin category: {BIN_CATEGORY_MAP[material]}")

        parts.append(f"\n{first_sent} {citation(top)}")

        # If the top paragraph has more than one sentence, append the rest as
        # supporting facts, each cited.
        rest = self._remaining_sentences(top_text)
        if rest:
            parts.append(f"\nSupporting details: {rest} {citation(top)}")

        # If there is a second relevant entry, add it as a secondary source.
        if len(retrieved) > 1:
            second = retrieved[1]["entry"]
            # Only include if it adds new info (different source or different angle).
            if second["id"] != top["id"]:
                sec_sent = self._first_sentence(second["text"])
                # Skip secondary notes that are clearly off-topic (e.g. rewards list).
                if len(sec_sent) > 15 and "reward" not in sec_sent.lower() and "points" not in sec_sent.lower():
                    parts.append(f"\nAdditional note: {sec_sent} {citation(second)}")

        return "\n".join(parts)

    def _build_general_rule(self, question: str, retrieved: List[Dict[str, Any]]) -> str:
        if not retrieved:
            return ""
        top = retrieved[0]["entry"]
        sent = self._first_sentence(top["text"])
        return f"{sent} {citation(top)}"

    def _build_hazardous_excerpts(self, retrieved: List[Dict[str, Any]]) -> str:
        if not retrieved:
            return ""
        lines = []
        for item in retrieved[:2]:
            e = item["entry"]
            lines.append(f"- {e['text'].split(chr(10))[0]} {citation(e)}")
        return "\n".join(lines)

    def _build_caveat_reminder(self, question: str, retrieved: List[Dict[str, Any]]) -> str:
        """Build a situation-specific caveat reminder for non-hazardous caveat cases."""
        lower = question.lower()
        reminders = []
        if "glass" in lower and "clean" not in lower:
            reminders.append(
                "Glass bottles are only accepted at designated glass recycling points "
                "(re Kiosk, or the smart bins at G/F Central Podium Levels and Pine Court). "
                "Not all smart bins accept glass."
            )
        if any(k in lower for k in ["milk tea", "takeaway", "take away", "take-out", "takeout", "container", "cup"]):
            reminders.append(
                "Rinse the container and remove food residue before recycling. "
                "Greasy or food-contaminated items go to general refuse, not recycling bins."
            )
        if any(k in lower for k in ["greasy", "grease", "contaminated", "food residue", "food-contaminated"]):
            reminders.append(
                "Contaminated items cannot be recycled and should go to general refuse. "
                "Only clean and dry items go into recycling bins."
            )
        if any(k in lower for k in ["coated paper", "paper cup", "plastic-coated"]):
            reminders.append(
                "Plastic-coated paper cups are usually not recyclable because of the "
                "plastic lining. Follow the official guidance and on-site signage."
            )
        if any(k in lower for k in ["leftover food", "food waste", "canteen"]):
            reminders.append(
                "There is no campus-wide unified food waste recycling standard. "
                "Arrangements depend on the canteen or hall; follow on-site signs."
            )
        if any(k in lower for k in ["hall", "halls", "residence"]):
            reminders.append(
                "Hall recycling rules may differ from the main campus. "
                "Follow the on-site signs in your hall, which take precedence."
            )
        if any(k in lower for k in ["smart recycling machine", "smart machine"]) or \
           ("smart bin" in lower and any(p in lower for p in ["does not accept", "not accepted", "won't accept"])):
            reminders.append(
                "If a smart recycling machine does not accept an item, it does not "
                "mean the item is not recyclable. Take it to the appropriate "
                "designated recycling point (e.g. re Kiosk)."
            )
        if not reminders:
            reminders.append("Follow on-site signage for any location-specific rules.")
        return " ".join(reminders)

    def _collect_citations(self, retrieved: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen = set()
        out = []
        for item in retrieved:
            e = item["entry"]
            if e["id"] in seen:
                continue
            seen.add(e["id"])
            out.append({
                "id": e["id"],
                "source_title": e["source_title"],
                "paragraph": e["paragraph"],
                "url": e["url"],
                "organization": e.get("organization", ""),
                "excerpt": e["text"][:300],
            })
        return out

    # ------------------------------------------------------------------
    @staticmethod
    def _first_sentence(text: str) -> str:
        text = text.strip()
        # Strip leading quiz labels like "Q8. " or "Q12. " before extracting.
        text = re.sub(r"^Q\d+\.\s*", "", text)
        # Take the first line if it's a heading, else first sentence.
        lines = text.split("\n")
        first_line = lines[0].strip()
        if len(lines) > 1 and len(first_line) < 60 and not first_line.endswith((".", "?", "!")):
            # Heading + content: use the first sentence of the content.
            content = " ".join(lines[1:]).strip()
            m = re.match(r"(.+?[.!?])", content)
            if m:
                return m.group(1).strip()
            return content[:200].strip()
        # Otherwise, first sentence of the whole text.
        m = re.match(r"(.+?[.!?])", text.replace("\n", " "))
        if m:
            return m.group(1).strip()
        return text[:200].strip()

    @staticmethod
    def _remaining_sentences(text: str) -> str:
        text = text.strip()
        # Strip leading quiz labels like "Q8. " before extracting.
        text = re.sub(r"^Q\d+\.\s*", "", text)
        lines = text.split("\n")
        first_line = lines[0].strip()
        if len(lines) > 1 and len(first_line) < 60 and not first_line.endswith((".", "?", "!")):
            content = " ".join(lines[1:]).strip()
        else:
            content = text.replace("\n", " ")
        m = re.match(r"(.+?[.!?])", content)
        if m:
            rest = content[m.end():].strip()
            return rest[:300]
        return ""

    # ------------------------------------------------------------------
    def _generate_llm(self, question: str, retrieved: List[Dict[str, Any]]) -> Optional[str]:
        """Call an OpenAI-compatible chat endpoint. Returns None on failure."""
        context_lines = []
        for item in retrieved[:3]:
            e = item["entry"]
            context_lines.append(f"[{e['id']}] {e['text']}")
        context = "\n\n".join(context_lines)

        prompt = (
            "You are a recycling assistant for the HKU campus. Answer the user's "
            "question using ONLY the provided context. Every factual claim must "
            "be followed by a citation in square brackets, e.g. [recycling_101#7]. "
            "Do not invent information. If the context does not contain enough "
            "basis to answer, say you cannot answer. Keep the answer concise and "
            "in plain English. Start by stating the bin category if applicable.\n\n"
            f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"
        )

        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 400,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.api_base.rstrip('/')}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["choices"][0]["message"]["content"].strip()
        except (urllib.error.URLError, urllib.error.HTTPError, KeyError,
                TimeoutError, OSError, json.JSONDecodeError) as e:
            print(f"[generator] LLM call failed: {e}", file=sys.stderr)
            return None


def main():
    from boundary import classify_question
    from retriever import Retriever

    r = Retriever()
    g = Generator()

    questions = [
        "Where does plastic go at HKU?",
        "Which bin does an aluminium can go into?",
        "Where can I recycle glass bottles on campus?",
        "How do I dispose of used AA batteries?",
        "Where do I put an old phone charger?",
    ]
    for q in questions:
        decision = classify_question(q)
        retrieved = r.retrieve(q, top_k=3) if decision.action in ("answer", "defer", "answer_with_caveat") else []
        result = g.generate(q, retrieved, decision)
        print(f"Q: {q}")
        print(f"  action: {result['action']} | cache: {result['used_cache']} | llm: {result['used_llm']}")
        print(f"  answer: {result['answer'][:300]}")
        if result["citations"]:
            print(f"  citations: {[c['id'] for c in result['citations']]}")
        print()


if __name__ == "__main__":
    main()

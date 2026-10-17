"""
boundary.py - Online Q&A Pipeline Step 1: Boundary / Rule Layer

Decides how the system should handle a user question BEFORE retrieval runs.
It classifies the question into one of these actions:

  - "answer"           : normal retrieval + generation
  - "answer_with_caveat": hazardous waste (batteries, fluorescent tubes,
                          expired medication). Only official source excerpts
                          are returned - never step-by-step disposal advice.
  - "defer"            : on-site signage / staff instruction conflicts with
                          the system answer. The system defers to on-site
                          guidance and explains the general rule.
  - "refuse"           : out of scope (off-campus, fines/appeals, waste
                          disposal applications, items with no campus-wide
                          unified standard). The system politely refuses and
                          explains why / where to get help.

The rule layer is intentionally keyword + pattern based. It runs first so
that out-of-scope or dangerous questions never reach the generator.

Usage (as a module):
    from boundary import classify_question
    decision = classify_question("Where can I throw a plastic bottle at HKU?")
    # decision.action, decision.reason, decision.refusal_message
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BoundaryDecision:
    action: str  # answer | answer_with_caveat | defer | refuse
    reason: str = ""
    refusal_message: str = ""
    defer_message: str = ""
    caveat_message: str = ""
    hall_tutor_hint: bool = False
    hazardous: bool = False
    matched_keywords: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Keyword sets
# ---------------------------------------------------------------------------

# Off-campus triggers: places outside HKU, general HK / domestic waste questions
OFF_CAMPUS_KEYWORDS = [
    "causeway bay", "central", "mong kok", "tsim sha tsui", "kowloon",
    "new territories", "lantau", "sha tin", "tai po", "tuen mun",
    "yuen long", "north point", "wan chai", "admiralty", "sheung wan",
    "sai ying pun", "shek tong tsui", "kenedy town", " Aberdeen",
    "home", "at home", "household", "my house", "my flat", "my apartment",
    "off campus", "off-campus", "outside campus", "outside hku",
    "public estate", "my estate", "housing estate",
    "hong kong's overall", "hong kong overall", "waste charging policy",
    "municipal solid waste charging", "territory-wide", "territory wide",
    "city-wide", "city wide", "all of hong kong",
]

# Penalty / appeal / fine triggers
PENALTY_KEYWORDS = [
    "fine", "fined", "penalty", "appeal", "appealing", "ticket",
    "summons", "charged", "prosecute", "prosecution", "discipline",
    "disciplinary", "hearing", "violation ticket", "littering ticket",
]

# Waste disposal application / formal collection request triggers
APPLICATION_KEYWORDS = [
    "apply for", "application", "request a collection", "book a collection",
    "schedule a pickup", "bulky waste collection", "remove my",
    "disposal application", "collection service", "pick up my",
]

# Items WITHOUT a campus-wide unified standard -> refuse + hall tutor hint
NO_STANDARD_ITEMS = [
    "phone charger", "charger", "power adapter", "charging cable",
    "small electrical appliance", "small appliance", "broken fan",
    "hair dryer", "vacuum cleaner", "microwave", "kettle", "toaster",
    "bulky furniture", "mattress", "sofa", "bed frame", "wardrobe",
    "desk", "chair", "furniture",
    "ceramic", "porcelain", "ceramic cup", "ceramic tableware",
    "old clothes", "used clothes", "textile", "clothing", "donate clothes",
]

# Hazardous waste -> answer_with_caveat (official guidance only)
HAZARDOUS_ITEMS = [
    "battery", "batteries", "aa battery", "aaa battery", "rechargeable battery",
    "fluorescent tube", "fluorescent light", "cfl", "light bulb",
    "expired medication", "expired medicine", "unused medication",
    "unused medicine", "pills", "tablets", "syringe", "needles",
    "chemical", "solvent", "paint", "pesticide",
]

# On-site signage / staff conflict triggers -> defer
DEFER_KEYWORDS = [
    "sign says", "signage says", "the sign", "floor sign",
    "cleaner says", "cleaner told", "staff says", "staff told",
    "contradict", "contradicts", "contradiction", "conflict",
    "but you said", "but the app said", "who should i follow",
    "which do i follow", "who is right", "which is correct",
    "on-site", "on site",
]

# Items that need a caveat (special condition: location restriction, rinsing,
# contamination, no unified standard within a category, hall rule differences).
# These get answer_with_caveat instead of plain answer.
CAVEAT_KEYWORDS = [
    "milk tea", "bubble tea",
    "takeaway", "take away", "take-out", "takeout",
    "greasy", "grease", "contaminated", "food residue", "food-contaminated",
    "leftover food", "food waste", "canteen food",
    "coated paper", "paper cup", "plastic-coated",
    "hall", "halls", "residence",
    "smart recycling machine", "smart machine",
    "smart bin",  # only when combined with "not accept" below
]

# Specific phrases that force a caveat (e.g. smart machine rejecting items)
CAVEAT_PHRASES = [
    "does not accept", "do not accept", "not accepted", "won't accept",
    "cannot be recycled", "can not be recycled", "not recyclable",
]


def _needs_caveat(text: str) -> bool:
    """Detect whether the question describes a situation that needs a caveat.

    Glass gets a caveat (location restriction) unless the item is explicitly
    described as clean.
    """
    lower = text.lower()
    # Glass: caveat unless explicitly "clean"
    if "glass" in lower and "clean" not in lower:
        return True
    if any(kw in lower for kw in CAVEAT_KEYWORDS):
        # "smart bin" only triggers caveat when the machine is rejecting something
        if "smart bin" in lower and not any(p in lower for p in CAVEAT_PHRASES):
            # smart bin alone is fine; check for rejection phrasing
            pass
        else:
            return True
    if any(p in lower for p in CAVEAT_PHRASES):
        return True
    return False


def _match_any(text: str, keywords: List[str]) -> List[str]:
    """Match keywords against text.

    Single-word keywords use word-boundary matching so that short words like
    "can" do not match inside "canteen" or the English verb "can".
    Multi-word phrases use substring matching.
    """
    lower = text.lower()
    matched = []
    for kw in keywords:
        if " " in kw or "-" in kw:
            # Multi-word phrase: substring match.
            if kw in lower:
                matched.append(kw)
        else:
            # Single word: word-boundary match.
            if re.search(r"\b" + re.escape(kw) + r"\b", lower):
                matched.append(kw)
    return matched


def classify_question(question: str) -> BoundaryDecision:
    """Classify a user question into a boundary action."""
    q = question.strip()
    lower = q.lower()

    # --- Hazardous waste (answer_with_caveat) ---
    # Check this BEFORE no-standard, because "battery" etc. need caveat not refuse.
    haz = _match_any(q, HAZARDOUS_ITEMS)
    if haz:
        return BoundaryDecision(
            action="answer_with_caveat",
            reason=f"Hazardous waste detected: {', '.join(haz)}",
            caveat_message=(
                "This item is classified as hazardous waste. I can only provide "
                "official source excerpts and guidance links - I will not give "
                "step-by-step disposal advice. Please follow the official "
                "designated collection procedures."
            ),
            hazardous=True,
            matched_keywords=haz,
        )

    # --- On-site signage / staff conflict (defer) ---
    defer = _match_any(q, DEFER_KEYWORDS)
    if defer:
        return BoundaryDecision(
            action="defer",
            reason=f"On-site signage/staff conflict detected: {', '.join(defer)}",
            defer_message=(
                "On-site signage and staff instructions always take precedence. "
                "When the sign or a cleaner on your floor says otherwise, "
                "follow the on-site sign/staff. I can still explain the general "
                "campus rule, but the on-site instruction is the deciding factor."
            ),
            matched_keywords=defer,
        )

    # --- Off-campus (refuse) ---
    off = _match_any(q, OFF_CAMPUS_KEYWORDS)
    if off:
        return BoundaryDecision(
            action="refuse",
            reason=f"Off-campus / out-of-scope question: {', '.join(off)}",
            refusal_message=(
                "This question is outside the HKU campus scope. I can only "
                "answer questions about waste sorting and recycling on the HKU "
                "campus. For off-campus or household waste sorting, please refer "
                "to the Waste Reduction website of the Environmental Protection "
                "Department (https://www.wastereduction.gov.hk)."
            ),
            matched_keywords=off,
        )

    # --- Penalty / appeal (refuse) ---
    pen = _match_any(q, PENALTY_KEYWORDS)
    if pen:
        return BoundaryDecision(
            action="refuse",
            reason=f"Penalty/appeal question: {', '.join(pen)}",
            refusal_message=(
                "I cannot help with penalty appeals, fines, or disciplinary "
                "procedures. These matters are handled by the relevant "
                "university or government authorities. Please contact the "
                "appropriate office directly."
            ),
            matched_keywords=pen,
        )

    # --- Waste disposal application (refuse) ---
    app = _match_any(q, APPLICATION_KEYWORDS)
    if app:
        return BoundaryDecision(
            action="refuse",
            reason=f"Waste disposal application/collection request: {', '.join(app)}",
            refusal_message=(
                "I cannot process waste disposal applications or formal "
                "collection requests. Please contact the Estates Office or your "
                "hall office to arrange collection services."
            ),
            matched_keywords=app,
        )

    # --- No campus-wide unified standard (refuse + hall tutor hint) ---
    nostd = _match_any(q, NO_STANDARD_ITEMS)
    if nostd:
        return BoundaryDecision(
            action="refuse",
            reason=f"No campus-wide unified standard for: {', '.join(nostd)}",
            refusal_message=(
                f"There is no campus-wide unified standard for {', '.join(nostd)}. "
                "I cannot give a definitive bin category for this item. "
                "Please consult your hall tutor or hall office for guidance on "
                "how to handle it in your residence."
            ),
            hall_tutor_hint=True,
            matched_keywords=nostd,
        )

    # --- Caveat items (answer with an extra condition/warning) ---
    if _needs_caveat(q):
        return BoundaryDecision(
            action="answer_with_caveat",
            reason="Item/situation requires a special caveat (location, cleaning, contamination, or hall-rule difference).",
            caveat_message=(
                "This question involves a situation with special conditions "
                "(e.g. location restriction, cleaning requirement, "
                "contamination, or hall-specific rules). I will answer based "
                "on the official documents and include the relevant caveat."
            ),
        )

    # --- Default: answer normally ---
    return BoundaryDecision(action="answer", reason="In-scope recycling question.")


def main():
    """Quick interactive test of the boundary rules."""
    tests = [
        "Where can I throw plastic at HKU?",
        "I'm in Causeway Bay, where can I throw this plastic bottle?",
        "I was fined for littering, can you help me appeal?",
        "Where do I put an old phone charger?",
        "How do I dispose of used AA batteries?",
        "The floor sign says no plastic bottles but you said yes, who do I follow?",
        "Where should I take an old mattress?",
        "Which bin does an aluminium can go into?",
    ]
    for t in tests:
        d = classify_question(t)
        print(f"Q: {t}")
        print(f"   -> action={d.action} | reason={d.reason}")
        print()


if __name__ == "__main__":
    main()

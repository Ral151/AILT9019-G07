# Retrieval threshold calibration (dev split)

- Run: 2026-10-18 03:20
- Embedding model: `BAAI/bge-small-en-v1.5`, corpus `2026-10-18.1`
- Positives: 19 (min 0.614, median 0.744); negatives: 10 (max 0.697)
- **Recommended RETRIEVE_TAU = 0.688** (balanced accuracy 0.90; at tau: TPR 0.89, TNR 0.90)

Scores overlap, so tau is a coarse filter. Questions the corpus does not cover but
that score above tau are caught by the answer model's `answers_question=false`
(-> LOW_RETRIEVAL_MATCH) and off-topic ones by the intent call.

| case | label | top-1 score | top-1 chunk | question |
|---|---|---|---|---|
| D-015 | pos | 0.928 | guide-plastic-dont-3 | Can I recycle a toothpaste tube? |
| D-013 | pos | 0.894 | quiz-q14-plastic-points | How many GreenU points do I get for recycling plastic bottles? |
| D-011 | pos | 0.875 | poster-paper-dont-6 | Can I recycle used napkins? |
| D-017 | pos | 0.870 | poster-paper-do-3 | Can I recycle a toilet paper roll core? |
| D-028 | pos | 0.827 | poster-plastic-do-1 | Where should I put an empty plastic water bottle? |
| D-016 | pos | 0.820 | poster-paper-do-4 | Are standard paper business cards recyclable? |
| D-024 | pos | 0.787 | guide-metal-dont-4 | Where should I put an empty beer bottle? |
| D-012 | pos | 0.762 | kiosk-accepts-tetra | Where is the re Kiosk? |
| D-001 | pos | 0.745 | poster-plastic-dont-4 | Where does plastic go? |
| D-027 | pos | 0.744 | poster-plastic-do-4 | Can I recycle an empty body wash bottle? |
| D-010 | pos | 0.731 | guide-plastic-do-6 | Can I recycle styrofoam? |
| D-002 | pos | 0.719 | poster-plastic-dont-4 | Does a Coke bottle go in the metal category? |
| D-014 | pos | 0.719 | kiosk-accepts-glass | Can I recycle a soy sauce glass bottle? |
| D-030 | pos | 0.715 | poster-paper-do-1 | Can I recycle old magazines and publications? |
| D-036 | neg | 0.697 | guide-paper-dont-5 | Can I recycle an old towel? |
| D-032 | pos | 0.694 | check-paper-1 | Can I recycle an old CD? |
| D-025 | pos | 0.692 | kiosk-accepts-glass | Can I recycle an empty glass jam jar? |
| D-031 | pos | 0.690 | poster-tetra-do-1 | Where do I recycle a carton box? |
| D-022 | neg | 0.685 | poster-plastic-do-3 | Can I recycle wooden chopsticks? |
| D-034 | neg | 0.624 | poster-paper-do-6 | Where do I put used cat litter? |
| D-026 | pos | 0.623 | guide-metal-dont-2 | Where do empty soup tins go? |
| D-023 | neg | 0.621 | quiz-q1-main-campus-bins | What's the best restaurant near HKU? |
| D-020 | neg | 0.621 | poster-tetra-do-2 | Where can I recycle coffee grounds? |
| D-035 | neg | 0.619 | guide-paper-do-1 | Can I recycle a used tea bag? |
| D-029 | pos | 0.614 | poster-plastic-do-2 | Where does an empty juice box go? |
| D-021 | neg | 0.607 | guide-paper-dont-5 | Can I recycle an old pillow? |
| D-033 | neg | 0.584 | poster-paper-dont-5 | Can I recycle a used candle? |
| D-019 | neg | 0.578 | poster-plastic-dont-5 | Can I recycle a yoga mat? |
| D-018 | neg | 0.565 | guide-paper-dont-1 | Can I recycle a broken umbrella? |

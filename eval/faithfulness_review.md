# Manual faithfulness review (release gate, §9.2 / §9.5)

Status: signed off

Before release, review at least 10 answer-path cases from a `--split test`
report. For each, confirm that every factual claim in `answer_text` is stated
in the cited excerpts, and that the bin category matches them.

Reviewers: Wu Haoyang (2026-10-23; re-reviewed 2026-11-06 after the answer-prompt change); image cases reviewed 2026-11-16 (sign-off pending)

| case | report file | claim-level faithful? (y/n) | notes | reviewer |
|---|---|---|---|---|
| T-001 | test-20261106-224054.md | y | "Plastic bin" + "Beverage plastic bottles" both in cited excerpt | Wu Haoyang |
| T-002 | test-20261106-224054.md | y | "Metal bin" matches "Aluminium cans and iron cans" | Wu Haoyang |
| T-003 | test-20261106-224054.md | y | "Paper bin" matches "Brochures · Publications · Books" | Wu Haoyang |
| T-004 | test-20261106-224054.md | y | "Glass Bottle bin" matches cited "Glass Bottle" | Wu Haoyang |
| T-005 | test-20261106-224054.md | y | "Tetra Pak bin" matches "Paper Cups" (listed under Tetra Pak DOs); "do not put in the Paper bin" matches "Paper tableware" (Paper DON'Ts) | Wu Haoyang |
| T-006 | test-20261106-224054.md | y | "Takeaway plastic boxes" + "rinsed and dried" both supported by the two cited excerpts | Wu Haoyang |
| T-007 | test-20261106-224054.md | y | "Plastic bin" matches "Plastics bottles for personal care products" | Wu Haoyang |
| T-008 | test-20261106-224054.md | y | "Plastic bin" matches "Plastic utensils" | Wu Haoyang |
| T-009 | test-20261106-224054.md | y | "Paper bin" matches "Corrugated paper" | Wu Haoyang |
| T-010 | test-20261106-224054.md | y | "Paper bin" matches "Envelopes · Letter paper" | Wu Haoyang |
| T-011 | test-20261106-224054.md | y | "Metal bin" matches "Aluminium cans and iron cans" | Wu Haoyang |
| T-012 | test-20261106-224054.md | y | "Tetra Pak bin" + "Tetra Pak cartons" match "All types of Tetra Pak Cartons" | Wu Haoyang |
| T-030 | test-20261106-224054.md | y | bin_category null; "Aerosol cans" under Metal DON'Ts supports "do not put in the metal bin" (listed_as_dont caveat) | Wu Haoyang |

## Image cases (vision milestone, §7)

The photo only names the item from a closed label list; the bin still comes
from retrieval + citation, so the same faithfulness rule applies to the answer
path.

| case | report file | claim-level faithful? (y/n) | notes | reviewer |
|---|---|---|---|---|
| TI-001 | test-20261116-012144.md | y | "PET bottles" → Plastic; cited "Beverage plastic bottles" (r101_poster 31) |  |
| TI-002 | test-20261116-012144.md | y | "aluminium and iron cans" → Metal; cited r101_poster 22 / guide 22 |  |
| TI-003 | test-20261116-012144.md | y | "office paper…" → Paper; cites 6/10/48; correctly excludes paper cups |  |
| TI-004 | test-20261116-012144.md | y | "glass bottle" → Glass Bottle; cited re_facilities 9 |  |
| TI-005 | test-20261116-012144.md | y | "paper cups" → Tetra Pak; cited r101_poster 48 / guide 16 |  |
| TI-006 | test-20261116-012144.md | y | "carton" → Tetra Pak; cited "All types of Tetra Pak cartons" (47) |  |

Safety-path image cases verified against gold: TI-007 battery → hazardous
links; TI-009 charger / TI-010 fan → refuse; TI-011/TI-012 → unclear-image
defer; TI-013 no-item → clearer-input defer; TI-014/TI-015 → multi-item defer.

### VISION_MIN_CONF calibration (dev + test images, 2026-11-16)

Observed vision confidence on the clear items is 0.95–1.00 (lowest 0.90 for the
power bank misread as a charger). Blurry / dark / no-item photos are caught by
`image_quality` / `no_waste_item` before the confidence gate, so the provisional
`VISION_MIN_CONF = 0.7` and `VISION_MARGIN = 0.15` leave a comfortable margin —
kept as-is.

### Known limitation (image, not a faithfulness issue)

TI-008 (power bank): the vision model recognises the power bank as
`phone charger` / `small electrical appliance` (≈0.90), so the pipeline refuses
(`NO_UNIFIED_STANDARD`) instead of deferring to hazardous links as the gold
expects. The policy treats "power bank" as hazardous, but the closed vision
label list has no `power bank` label and the model cannot visually tell a power
bank from a charger. Left open for the team (add a `power bank` vision label +
policy mapping, or change the gold to the refuse outcome).

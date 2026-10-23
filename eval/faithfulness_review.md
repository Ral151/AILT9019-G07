# Manual faithfulness review (release gate, §9.2 / §9.5)

Status: signed off

Before release, review at least 10 answer-path cases from a `--split test`
report. For each, confirm that every factual claim in `answer_text` is stated
in the cited excerpts, and that the bin category matches them.

Reviewers: Wu Haoyang (2026-10-23)

| case | report file | claim-level faithful? (y/n) | notes | reviewer |
|---|---|---|---|---|
| T-001 | test-20261023-230242.md | y | "Plastic bin" + "Beverage plastic bottles" both in cited excerpt | Wu Haoyang |
| T-002 | test-20261023-230242.md | y | "Metal bin" matches "Aluminium cans and iron cans" | Wu Haoyang |
| T-003 | test-20261023-230242.md | y | "Paper bin" matches "Brochures · Publications · Books" | Wu Haoyang |
| T-004 | test-20261023-230242.md | y | "Glass Bottle bin" matches cited "Glass Bottle" | Wu Haoyang |
| T-005 | test-20261023-230242.md | y | "Tetra Pak bin" matches "Paper Cups" (poster lists Paper Cups under Tetra Pak DOs) | Wu Haoyang |
| T-006 | test-20261023-230242.md | y | "Takeaway plastic boxes" + "rinsed and dried" both supported by the two cited excerpts | Wu Haoyang |
| T-007 | test-20261023-230242.md | y | "Plastic bin" matches "Plastics bottles for personal care products" | Wu Haoyang |
| T-008 | test-20261023-230242.md | y | "Plastic bin" matches "Plastic utensils" | Wu Haoyang |
| T-009 | test-20261023-230242.md | y | "Paper bin" matches "Corrugated paper" | Wu Haoyang |
| T-010 | test-20261023-230242.md | y | "Paper bin" matches "Envelopes · Letter paper" | Wu Haoyang |
| T-011 | test-20261023-230242.md | y | "Metal bin" matches "Aluminium cans and iron cans" | Wu Haoyang |

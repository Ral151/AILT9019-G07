# Manual faithfulness review (release gate, §9.2 / §9.5)

Status: not started

Before release, review at least 10 answer-path cases from a `--split test`
report. For each, confirm that every factual claim in `answer_text` is stated
in the cited excerpts, and that the bin category matches them.

When all rows pass, change the first line to `Status: signed off` and add the
reviewers' names. `python -m eval.run_eval --split test` checks for that line.

| case | report file | claim-level faithful? (y/n) | notes | reviewer |
|---|---|---|---|---|
|  |  |  |  |  |

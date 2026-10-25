# Partial evaluation — eval-20261024-192400

This iteration was stopped after 11 of 24 personas; it is not a complete suite result. The first ten matched their expected outcomes except SYN007, which was conservatively escalated to Flagged after the screener raised a coordinator concern for an underage candidate. SYN011 exposed an exclusion-verdict error: the candidate reported regular overnight work, but C8 was recorded as satisfied. The screening token estimate also hit the configured per-candidate cap near the end of that run.

The screener prompt now explicitly defines verdicts against the full requirement (“must NOT” exclusion facts are not satisfied), and only the current question/answer is sent as variable history; older transcript turns remain in SQLite. A test guards the exclusion instruction. This partial run is retained as iteration evidence; use the later complete run for final metrics.

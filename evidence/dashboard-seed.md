# Synthetic coordinator dashboard seed

Seeded on 2026-10-24 with:

```text
python -m scripts.seed_demo_dashboard
```

The idempotent seeder added 24 completed examples (`demo-SYN001`–`demo-SYN024`) to the local SQLite database. It preserved the two pre-existing demo sessions. The final database contains 26 candidates: 25 completed and 1 still in progress.

The candidate messages and criterion evidence come from the fictional persona bank. The app's code computed each displayed status from chat-checkable verdicts; no answer-key labels were copied into candidate decisions. Current seeded status mix:

| Status | Synthetic examples |
|---|---:|
| Likely eligible | 10 |
| Not a match | 7 |
| Needs review | 4 |
| Flagged | 3 |

This table is the historical pre-fix snapshot. A fresh seed under the all-criteria policy now yields 3 Flagged, 14 Needs review, and 7 Not a match; likely-eligible examples remain in review until required clinic confirmations are recorded. The revised seed-count regression test passes with this new distribution.

No live model calls, tokens, or API costs were generated. The dashboard labels these as preloaded synthetic examples. Existing coordinator approvals/contact actions were not fabricated. The three injection personas passed through the app's injection-pattern check and created coordinator-visible safety events.

The seed uses only fictional persona facts and deliberately does not load the evaluator-only answer key. Clinic-confirmation items are now stored as unclear self-reports, not passed off as checked results. On a fresh seed under this policy, candidates needing clinic confirmation remain Needs review until a coordinator records the review. Existing local seeded records are historical and are not rewritten automatically.

The app now asks all 12 protocol questions, including the five that require clinic confirmation. Their evidence cards clearly label answers as self-reported and pending confirmation.

Verification for the historical seed: `116 passed` in the full pytest suite; home, coordinator, and participant routes returned HTTP 200 through Flask's test client. Current regression results are recorded in `evidence/agent-2-screening.md`.

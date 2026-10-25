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

No live model calls, tokens, or API costs were generated. The dashboard labels these as preloaded synthetic examples. Existing coordinator approvals/contact actions were not fabricated. The three injection personas passed through the app's injection-pattern check and created coordinator-visible safety events.

The seed uses only chat-checkable persona facts and deliberately does not load the evaluator-only answer key. SYN014's C2 and SYN019's C9 facts are clinic-only and therefore are not inserted as chat verdicts; their displayed status is based only on the chat-screenable criteria. This is why the dashboard's code-derived status mix is not the same as the answer-key distribution.

Verification: `116 passed` in the full pytest suite; home, coordinator, and participant routes returned HTTP 200 through Flask's test client.

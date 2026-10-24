# Agent 2 screening evidence

Captured 2026-10-24 from the committed offline simulation and the real Portkey smoke run. All persona details are synthetic.

## Offline end-to-end chat

Command: `python -m scripts.simulate_screening`

The mocked conversation started with age, accepted an exact quote, and ignored an instruction embedded in the candidate message. It then requested height and weight, calculated BMI from the reported values, asked a follow-up when medication use was vague, and clarified a tentative willingness response. The script persisted these criterion-level answers in its temporary SQLite database:

| Criterion | Verdict | Exact evidence quote |
| --- | --- | --- |
| C1 | met | `I'm 29` |
| C3 | met | `I'm 170 cm and 68 kg` |
| C4 | unknown | `twice a week` |
| C5 | met | `I am willing to follow the visits and instructions` |

The BMI tool returned 23.5. C2 was clinic-only and did not appear in the chat. The simulation also confirmed messages and answers are stored, the untrusted instruction is not repeated in the assistant reply, and follow-up questions do not advance progress prematurely.

## Live model run

The separate real smoke run used `gpt-6-luna` through Portkey with a made-up persona and a temporary candidate database. Its seven API calls are recorded in `logs/usage.jsonl` (candidate ID `4933731c-2bae-49ac-8010-d3c7216dc28f`):

- Input tokens: 9,693
- Cached input tokens: 6,244
- Output tokens: 329
- Estimated logged cost: $0.00165135
- API calls: 7

These are observed totals for that short run, not a full screening's unit cost. Prices are the configured estimates; see `config/pricing.json` and README for the cached-input placeholder caveat. The temporary live-run candidate database was deleted automatically when the smoke script exited; its usage records contain only the synthetic candidate identifier and aggregate call metadata.

## Automated safety checks

`python -m pytest -q` verifies that fabricated evidence quotes are rejected, a generated eligibility/medical claim is replaced by a safe response, token-budget exhaustion ends the chat neutrally, candidate messages are safely JSON-wrapped, and messages longer than 800 characters are rejected. The offline chat test also injects a request to reveal another candidate's information and verifies that it is not echoed or acted upon.

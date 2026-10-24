# Safety defense evidence

Captured 2026-10-24. All candidate examples in automated tests are synthetic; model calls are mocked.

## Verification run

- `.venv/bin/python -m pytest -q` — **92 passed**.
- Flask started with debug mode and reloader disabled on local port 5051. `/health`, `/coordinator`, `/coordinator/safety`, and `/screen` each returned HTTP 200. The existing process on port 5050 was not changed; this smoke-test process was stopped afterward.
- `git diff --check` — no whitespace errors.

## Defenses exercised

- Six representative prompt-injection phrases (instruction override, identity change, system prompt, eligibility manipulation, role-play, and other-candidate request) are recognized. A test then sends an override to `submit_candidate_message`, replaces the model function with a fail-fast mock, and proves no model call occurs. The candidate receives the neutral continuation response, their visible review status is Flagged, and the safety event contains the truncated excerpt.
- The medical-advice test similarly fails if the model is called. The candidate receives a doctor/study-team redirect plus the current screening question, with a `medical_advice_redirect` event.
- Existing verifier provenance tests submit a fabricated quote and confirm it is downgraded to unclear with the exact criterion note “Evidence not found in transcript” and a `verifier_quote_missing` event.
- Rate limiter tests confirm atomic rejection of a second message within two seconds and of a second start when the configured hourly cap is one. The route test checks the candidate-facing wait message and verifies the Safety page renders counters, the blocked action, and the truncated submitted text.
- The daily-budget route test checks the exact pause-for-today response and the coordinator's pause banner. Existing model-layer tests verify that turn, cumulative-token, character, tool-loop, and daily-dollar preflights stop provider calls and log safety events. The candidate chat displays returned pause/limit errors, and persisted daily-budget blocks remain visible after a refresh.
- A `flag_concern` test confirms the session is marked Flagged for coordinator review and creates a visible event. Existing Outreach and Insights tests verify their minimized tool surfaces exclude transcripts and candidate-level rows; existing coordinator tests verify approval/action gates and demo queueing never sends an email.
- A safety-log test verifies a key-like value in an offending excerpt is redacted before JSONL persistence.

The `/coordinator/safety` view now has event-type counters and a table with timestamp, candidate, event type, blocked action, and offending excerpt (capped at 180 characters and HTML-escaped). API-key-like values in excerpts are redacted before persistence.

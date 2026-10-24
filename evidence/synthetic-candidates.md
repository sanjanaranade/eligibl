# Synthetic candidate generation evidence

Captured 2026-10-24. All 24 personas and health details are fictional and generated for this classroom demo.

## Logged model run

`python -m scripts.generate_candidates` made six successful batches through `eligibl/llm.py`, logged as agent `generator` with model `gpt-6-luna`. The six successful calls used 11,938 input tokens, 0 cached input tokens, and 8,356 output tokens. Their estimated total cost in the current usage log is **$0.00680430**; this estimate uses the project's currently configured pricing, including its cached-input placeholder. Three earlier network-blocked attempts are also logged as errors with zero tokens and zero cost. No key or prompt text is written to the usage log.

## Dataset checks

- `data/synthetic/candidates.json`: 24 records, 12 criterion facts per persona, and a separate `special_test_message` field for each of the three attacks and two medical-advice interruptions.
- Frozen plan counts: 6 clearly eligible, 8 not a match, 5 borderline/unclear, 3 prompt-injection, and 2 medical-advice cases.
- The eight not-a-match cases each fail a different criterion. Seven target criteria the chat can assess; SYN014 targets C2, which requires clinic confirmation. Its ground truth is a protocol-level not-match, but the app should defer it until a coordinator/clinic review rather than claim the chat detected it.
- Set A and Set B are disjoint, each with two eligible, two not-a-match, and one borderline persona.
- Automated regression tests check counts, facts, one-failure/one-unclear invariants, the balanced split, answer-key alignment, instruction/advice separation from ordinary criterion statements, and that the screener/verifier source does not read the synthetic files.

The model generated prose and candidate-style statements only. Planned truth labels, facts, outcomes, and reasons were fixed locally before the model call; afterward these were attached to the prose and written to the separate answer-key CSV. Output inspection found some attack/advice bleed into five ordinary statements; these were replaced by fact-only lines, and a regression check was added to catch this on future generation runs.

## Project verification

The full test suite passed: **96 passed**. Flask started with debug and reload disabled; `/health`, `/coordinator`, and `/screen` returned HTTP 200 on local port 5051. Port 5050 was already in use and left undisturbed; the smoke-check server was stopped afterward.

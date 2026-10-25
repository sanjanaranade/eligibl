# Eligibl

Eligibl is a prototype for clinical research coordinators to review candidate screening against study criteria. It is being built for MGT 409, AI Foundations for Managers (Yale, Fall 2026). All candidate data is synthetic.

## Run locally

1. Create and activate a virtual environment:

   ```sh
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install pinned dependencies:

   ```sh
   pip install -r requirements.txt
   ```

3. Set `PORTKEY_API_KEY` in a `.env` file. The app checks the repository root first, then the parent folder. The teaching staff can place `.env` beside the cloned repository. Never commit `.env`; `.env.example` lists the required key name.

4. Start the app:

   ```sh
   python app.py
   ```

5. Open <http://127.0.0.1:5050>.

The app uses `gpt-6-luna` through Portkey for model calls. The welcome page remains available when the key is missing and explains where to configure it. Check `/health` for app status and whether a key was found; it never returns the key itself.

## Development

Run the offline test suite with `pytest`. Model-call tests use a mock and do not contact Portkey.
To manually verify Portkey connectivity with a tiny request, activate the venv and run `python -m scripts.smoke_model`.

All model requests go through `eligibl/llm.py` and the Responses API. That layer supports function tools and JSON-schema responses, logs each API attempt to SQLite and `logs/usage.jsonl`, and writes one trace row per agent step. The trace records brief summaries and tool arguments; it does not store the full prompt in the usage log.

Runtime limits are in `config/limits.json`. `/api/usage/today` reports tokens and estimated cost against the $2 daily budget. Cost rates are in `config/pricing.json`: input and output rates were copied from the earlier Lecture 11 course implementation. A cached-input rate was not documented there, so it currently uses the regular input rate as a clearly marked conservative placeholder. Verify that rate before using costs as final evidence.

Budget preflight estimates prompt tokens from half the serialized UTF-8 byte count; actual provider-reported token counts are logged and used for cumulative candidate totals. The screener requests at most 700 output tokens per model call (the protocol parser retains the larger configured cap for its structured checklist).

The coordinator workspace includes a Protocol page at `/coordinator/protocol`. It parses the supplied ClinicalTrials.gov eligibility text into a validated, plain-language checklist, preserves source wording, marks criteria requiring clinic confirmation, and caches the result in `data/protocol.json` until the source file changes. Use **Re-parse protocol** to refresh it manually. This protocol parsing step does not make eligibility decisions. The synthetic candidate chat is available at `/screen`; it stores messages and criterion-level evidence in SQLite, asks one question at a time, and skips clinic-check criteria. Candidate-facing screens never display an eligibility result; a separate deterministic coordinator-only status is computed in code after verification. Outreach is draft-only and never sent. The completion UI notes that this demo does not send email or contact anyone.

The coordinator dashboard also reports analytics for screenings completed in the last seven days: stage counts and stage-to-stage conversion, most frequent not-satisfied criteria, and average turns, tokens, and model cost per completed screening. Today's token and estimated-cost totals use the configured timezone. These are aggregate statistics only. Chart.js is loaded from a CDN for charts; the same values remain available in plain HTML tables when the CDN is unavailable. **Summarize this week** runs Agent 5, which has exactly one registered tool (`get_funnel_stats`) and receives no candidate IDs, names, transcripts, or other candidate-level rows. It returns a validated 3–4 sentence PI summary and its call is recorded by the common model logger.

## Safety

- Candidate messages are treated as untrusted data. Before a message reaches the screener model, a rule-based check looks for instruction overrides, system-prompt requests, identity/role-play changes, attempts to manipulate eligibility, and requests about other candidates. A match is saved in the transcript, flagged for coordinator review, logged with a short excerpt, and answered with the neutral response “I can only ask the screening questions, so let's continue.” The model has no tool that changes the final status.
- Medical-advice requests are declined in code before the model call, redirected to the candidate's doctor or the study team, and logged. The existing post-generation output filter also catches accidental eligibility claims or medical directives before they are shown.
- The verifier checks every evidence quote against candidate-authored messages. An unsupported quote is downgraded to unclear with the exact note “Evidence not found in transcript”; the criterion card shows this note and the Safety log records the event.
- Cost and loop defenses are checked before provider calls: 15 screening turns per candidate, 800 characters per message, 25,000 tokens per candidate, five tool-call loops per agent turn, and the shared $2 daily model budget. Per-session replies are limited to one every two seconds; starts are capped at 30 per hour per direct client IP, stored only as a one-way hash. Rate/length/budget blocks are logged and surfaced in the chat; when a daily-budget block occurs, the chat says “Screening is paused for today. Please try again tomorrow.” and the coordinator dashboard shows a pause banner.
- Outreach receives only its four-field summary tool (never a transcript). Insights receives aggregate counts and metrics only. Tests assert both boundaries. Outreach drafts are created only after coordinator approval or a coordinator's not-a-match action. Email is never sent, and AI cannot approve candidates or set their final decision; deterministic code calculates the suggestion and a human coordinator reviews and acts.
- The `/coordinator/safety` page shows event counters and an audit table with time, candidate, event type, what was blocked, and offending text truncated to 180 characters. The excerpts are for this synthetic-data demo; do not enter real candidate data.

Run the integrated safety suite with `.venv/bin/python -m scripts.run_safety_tests`. It uses a separate SQLite test database for each scenario and deterministic fake model responses, then writes `evidence/safety/results.md`. Its synthetic defense events are appended to `logs/safety.jsonl` and mirrored into the app database so they appear on `/coordinator/safety`. The demo does not authenticate coordinator identities; queued items are marked demo-only and are never sent.

After the candidate finishes, the verifier first checks each evidence quote against candidate-authored messages (case/whitespace normalized with a 90% fuzzy threshold) and downgrades unsupported evidence to unclear. A separate model call may only downgrade a satisfied criterion to unclear and provides a short coordinator summary; it cannot upgrade answers or determine a final outcome. `eligibl/decision.py` applies the deterministic outcomes, and the coordinator dashboard at `/coordinator` provides transcript/evidence review, trace, and timestamped actions. Approving a candidate (after selecting a reminder-planning slot) or marking them not a match asks Agent 4, Outreach, to prepare minimal-context drafts. The editable `/coordinator/email-drafts` page validates the content and allows a coordinator to queue a demo draft; nothing is ever sent. Sample visit times and the fictional contact line are in `config/availability.json` and must be replaced for any real deployment. Queue status is separate from sent status; `sent_at` remains empty.

For the BMI criterion, the checklist asks candidates for height and weight with units. The screener can call the tested deterministic BMI calculation tool for metric and imperial measurements; missing measurements/units or a value exactly at a range endpoint (the protocol does not specify endpoint inclusion) remains unclear. The tool calculates only; it does not make an overall eligibility decision.

To verify the chat end to end without a key, run `python -m scripts.simulate_screening`; it uses a mocked model and a temporary SQLite database. For a brief real Portkey smoke run using only a made-up persona and a temporary candidate database, run `python -m scripts.live_screening_smoke`.

## Synthetic evaluation candidates

Run the full real-model evaluation with .venv/bin/python -m scripts.run_eval (or activate .venv and run python -m scripts.run_eval). The simulator, screener, and verifier use gpt-6-luna through the normal model layer; only the evaluation runner reads the answer key. Each timestamped folder under evidence/eval/ contains per-persona transcripts, product-only results.csv metrics, a summary/confusion table, and detailed usage/safety JSONL logs. Simulator calls are labeled simulator and excluded from product token and cost totals.

Run `.venv/bin/python -m scripts.generate_candidates` (or activate `.venv` and run `python -m scripts.generate_candidates`) to recreate `data/synthetic/candidates.json`, `answer_key.csv`, and `user_test_sets.json`. The generator first freezes all 24 planned outcomes and criterion facts in code, then uses the logged `generator` agent through `eligibl/llm.py` to write fictional backstories and natural-language statements. The model cannot choose or revise expected outcomes. All generation calls use only `gpt-6-luna` and appear in `logs/usage.jsonl` and the SQLite usage table.

The answer key is evaluator-only. The screener and verifier do not load any file under `data/synthetic/`; a regression test checks that boundary. The two user-test sets are disjoint and each contains two eligible, two not-a-match, and one borderline persona. SYN014's planned single failure is criterion C2, which requires clinic assessment; its answer-key note records the expected protocol-level outcome and reminds evaluators that the chat must defer that decision pending clinic/coordinator review.

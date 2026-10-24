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

After the candidate finishes, the verifier first checks each evidence quote against candidate-authored messages (case/whitespace normalized with a 90% fuzzy threshold) and downgrades unsupported evidence to unclear. A separate model call may only downgrade a satisfied criterion to unclear and provides a short coordinator summary; it cannot upgrade answers or determine a final outcome. `eligibl/decision.py` applies the deterministic outcomes, and the coordinator dashboard at `/coordinator` provides transcript/evidence review, trace, and timestamped actions. Approving a candidate (after selecting a reminder-planning slot) or marking them not a match asks Agent 4, Outreach, to prepare minimal-context drafts. The editable `/coordinator/email-drafts` page validates the content and allows a coordinator to queue a demo draft; nothing is ever sent. Sample visit times and the fictional contact line are in `config/availability.json` and must be replaced for any real deployment. Queue status is separate from sent status; `sent_at` remains empty.

For the BMI criterion, the checklist asks candidates for height and weight with units. The screener can call the tested deterministic BMI calculation tool for metric and imperial measurements; missing measurements/units or a value exactly at a range endpoint (the protocol does not specify endpoint inclusion) remains unclear. The tool calculates only; it does not make an overall eligibility decision.

To verify the chat end to end without a key, run `python -m scripts.simulate_screening`; it uses a mocked model and a temporary SQLite database. For a brief real Portkey smoke run using only a made-up persona and a temporary candidate database, run `python -m scripts.live_screening_smoke`.

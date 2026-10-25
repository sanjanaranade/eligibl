# Eligibl

Eligibl is a prototype where prospective participants answer study questions and research coordinators review the evidence against study criteria. It is being built for MGT 409, AI Foundations for Managers (Yale, Fall 2026). All candidate data is synthetic.

## Run locally (grader quick start)

Eligibl runs locally; it does not need hosting, Docker, Node, a separate database server, or a build step. It uses Python, Flask, SQLite (included with Python), and the Portkey API. Use Python 3.10 or newer and an internet connection for model-powered screening.

### 1. Clone the repo

If you are cloning it yourself, open a terminal in the folder where you keep projects and run:

```sh
git clone https://github.com/sanjanaranade/eligibl.git
cd eligibl
```

If the course staff already cloned the submission, open a terminal in the cloned `eligibl` folder instead. The commands below should be run from the folder containing `app.py` and `requirements.txt`.

### 2. Check Python and create a virtual environment

macOS/Linux:

```sh
python3 --version
python3 -m venv .venv
source .venv/bin/activate
```

Windows PowerShell:

```powershell
py -3 --version
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, use the venv's Python directly instead (shown in the install and run commands below). In Command Prompt, the activation command is `.venv\Scripts\activate.bat`.

### 3. Install the pinned Python packages

With the virtual environment activated, on any platform run:

```sh
python -m pip install -r requirements.txt
```

Or, without activating the environment, use `.venv/bin/python -m pip install -r requirements.txt` on macOS/Linux, or `.venv\Scripts\python.exe -m pip install -r requirements.txt` in Windows PowerShell. No other package manager or build command is required.

### 4. Make the Portkey key available

Model-powered screening uses the course-approved `gpt-6-luna` model through Portkey and requires the environment variable named exactly `PORTKEY_API_KEY`.

The app checks for `.env` in **two places, in this order**: first in the `eligibl` repo folder, then one folder above the repo. The course staff's key file can therefore sit beside the cloned repo, like this:

```text
submissions/
├── .env                 # provided by course staff; contains PORTKEY_API_KEY
└── eligibl/             # cloned repo; run the app from here
    ├── app.py
    ├── .env.example      # key name only; no secret value
    └── requirements.txt
```

When testing with your own key, you may instead put it in a local `.env` in the repo folder. Never paste a key into chat, commit `.env`, or replace the staff's parent `.env`. `.env.example` is only a list of required variable names; do not rename it to `.env` expecting it to contain a working key. The `.env` file is ignored by Git.

The app can start without a key, and `/health` reports whether a key was found without revealing it, but starting a screening or using AI features requires a valid key and an internet connection to Portkey. API calls use the course key and model budget; all example participant data is synthetic.

### 5. Start Eligibl

With the virtual environment activated:

```sh
python app.py
```

Without activation, run `.venv/bin/python app.py` on macOS/Linux or `.venv\Scripts\python.exe app.py` in Windows PowerShell. The app runs with debug mode off at <http://127.0.0.1:5050>. Leave this terminal open while using it, then press `Ctrl+C` there to stop the server.

Open these pages in your browser:

- Welcome: <http://127.0.0.1:5050/>
- Participant screening: <http://127.0.0.1:5050/screen>
- Coordinator dashboard: <http://127.0.0.1:5050/coordinator>
- Health check: <http://127.0.0.1:5050/health>

The health check should return JSON with `"ok": true` and `"model": "gpt-6-luna"`. `"api_key_found": true` means the environment variable was detected; it does not print or validate the key itself. On first launch, the app creates the local SQLite file at `data/eligibl.sqlite3` and automatically preloads 24 clearly labeled synthetic example screenings, including three coordinator-approved examples and nine sample email drafts. This is offline setup: it makes no model calls, and the drafts are not queued or sent. Automatic seeding happens only if the database has no candidates; later launches preserve existing records. The database itself is ignored by Git.

### Optional: deliberately reset the local demo data

No seed command is needed for a fresh clone: the first normal app launch seeds the examples automatically. If you intentionally want to replace the local candidate-linked records with the original 24 synthetic examples, run `python -m scripts.reset_demo_dashboard` from the repo folder. This explicit reset first backs up the existing database under the ignored `data/backups/` folder and retains model-call cost history. Do not use it if you need to keep existing participant records. The reset creates synthetic examples only, makes no model calls, and leaves all sample email drafts unqueued and unsent.

### Common startup issues

- **`python` or `python3` is not found:** install Python 3.10+ and reopen the terminal. On Windows, use `py -3` in place of `python3`.
- **`No module named flask` (or another dependency):** make sure the venv is activated, then rerun `python -m pip install -r requirements.txt` from the repo folder.
- **Port 5050 is already in use:** another Eligibl process may already be running. Stop it with `Ctrl+C` in its server terminal, then retry. The app is configured for port 5050.
- **The page says the key is missing:** confirm the staff `.env` is in the directory one level above `eligibl/` (or your own `.env` is in the repo), and that the variable name is exactly `PORTKEY_API_KEY`. Restart the app after changing `.env`. Never send the key in a screenshot or support message.
- **The key is found but model calls fail:** `/health` checks only that a nonempty value was found. A provider authentication, network, or budget error may still prevent model calls; check the coordinator Safety log and verify network access without displaying the key.

## Development

Run the offline test suite with `pytest`. Model-call tests use a mock and do not contact Portkey.
To manually verify Portkey connectivity with a tiny request, activate the venv and run `python -m scripts.smoke_model`.

All model requests go through `eligibl/llm.py` and the Responses API. That layer supports function tools and JSON-schema responses, logs each API attempt to SQLite and `logs/usage.jsonl`, and writes one trace row per agent step. The trace records brief summaries and tool arguments; it does not store the full prompt in the usage log.

Runtime limits are in `config/limits.json`. `/api/usage/today` reports tokens and estimated cost against the $2 daily budget. Cost rates are in `config/pricing.json`: input and output rates were copied from the earlier Lecture 11 course implementation. A cached-input rate was not documented there, so it currently uses the regular input rate as a clearly marked conservative placeholder. Verify that rate before using costs as final evidence.

Budget preflight estimates prompt tokens from half the serialized UTF-8 byte count; actual provider-reported token counts are logged and used for cumulative candidate totals. The screener requests at most 700 output tokens per model call (the protocol parser retains the larger configured cap for its structured checklist).

The coordinator workspace includes a Protocol page at `/coordinator/protocol`. It parses the supplied ClinicalTrials.gov eligibility text into a validated, plain-language checklist, preserves source wording, marks criteria requiring clinic confirmation, and caches the result in `data/protocol.json` until the source file changes. Use **Re-parse protocol** to refresh it manually. This protocol parsing step does not make eligibility decisions. The synthetic candidate chat is available at `/screen`; it stores messages and criterion-level evidence in SQLite and asks one question at a time across the checklist. Clinic-check criteria are asked about as self-reports but recorded as unclear until confirmed by a coordinator or clinic visit. For BMI, the screener can calculate from candidate-reported height and weight. Candidate-facing screens never display an eligibility result; a separate deterministic coordinator-only status is computed in code after verification. Outreach is draft-only and never sent. The completion UI notes that this demo does not send email or contact anyone.

The coordinator dashboard also reports analytics for screenings completed in the last seven days: stage counts and stage-to-stage conversion, most frequent not-satisfied criteria, and average turns, tokens, and model cost per completed screening. Today's token and estimated-cost totals use the configured timezone. These are aggregate statistics only. Chart.js is loaded from a CDN for charts; the same values remain available in plain HTML tables when the CDN is unavailable. **Summarize this week** runs Agent 5, which has exactly one registered tool (`get_funnel_stats`) and receives no candidate IDs, names, transcripts, or other candidate-level rows. It returns a validated 3–4 sentence PI summary and its call is recorded by the common model logger.

To preload an additive set of fictional personas without changing existing records, run `.venv/bin/python -m scripts.seed_demo_dashboard`. For the classroom mockup, run `.venv/bin/python -m scripts.reset_demo_dashboard`: it first saves a consistent SQLite backup under the ignored `data/backups/` folder, then replaces participant-linked records with the 24 synthetic personas. It retains model-call cost records, creates three clearly labeled coordinator approval examples (with a visible synthetic-only override note), and adds validated sample email drafts. Those drafts remain `draft`—nothing is queued or sent. Synthetic transcripts and sample emails use no live model calls.

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

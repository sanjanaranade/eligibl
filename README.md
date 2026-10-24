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

The current app remains at the core scaffold stage: welcome, coordinator and screening entry pages, health and usage endpoints, database schema, and centralized Portkey client. Screening and outreach workflows will be added in later steps. Email functionality is draft-only; the app does not send messages.

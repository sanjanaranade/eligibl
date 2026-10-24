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

The current scaffold includes the welcome page, coordinator and screening entry pages, health check, database schema, and centralized Portkey client. Screening and outreach workflows will be added in later steps. Email functionality is draft-only; the app does not send messages.

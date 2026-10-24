# Core app scaffold checks

Date: 2026-10-24

- Dependencies installed in the local `.venv` from pinned `requirements.txt`.
- Offline suite: `python -m pytest -q` — 8 passed.
- Startup: `python app.py` served on `127.0.0.1:5050` with debug mode off and no auto-reloader; stopped after the smoke check.
- Health smoke check: `GET /health` returned `ok: true`, `api_key_found: true`, and `model: gpt-6-luna`. The key value was not returned or logged.
- No live model call was made during scaffold setup. LLM behavior was tested with a mock.
- The first test run exposed incorrect root template/static paths; those paths were fixed before the passing run.

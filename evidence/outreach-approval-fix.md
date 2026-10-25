# Coordinator approval / outreach regression check

- Failure reproduced from the trace for `demo-SYN001`: all three generated drafts named their configured dates and times, but omitted the year and `ET` suffix that the validator required verbatim. Draft validation rejected all three, so the coordinator action correctly remained unsaved and no partial drafts were inserted.
- Fix: invitation validation now checks each configured slot's month/day and time; reminder validation checks the chosen slot's month/day and time. Date/time scheduling remains computed and enforced by application code.
- Regression coverage: `test_slot_safety_check_accepts_date_and_time_without_redundant_year_or_timezone` in `tests/test_outreach.py`.
- Verification: `.venv/bin/python -m pytest -q` — **117 passed**.
- Startup check: the app was already listening on port 5050; `GET /health` returned `ok: true` and `model: gpt-6-luna`. A second launch was correctly refused because the port was occupied.

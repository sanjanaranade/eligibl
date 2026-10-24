# Agent 5 Insights and analytics evidence

Captured 2026-10-24. Tests use synthetic candidate records; model calls are mocked.

## Verification

- `.venv/bin/python -m pytest -q` — **78 passed**.
- Flask startup smoke check with debug and reloader disabled on local port 5051: `/health` returned HTTP 200 and `{"ok":true,"api_key_found":true,"model":"gpt-6-luna"}`; `/coordinator` returned HTTP 200.
- Port 5050 was already occupied by an existing Python listener, so it was left untouched. The smoke-check server was stopped after requests completed.
- No live model call was made for these tests.

## Analytics and privacy checks

The seven-day metrics test seeded synthetic completed records and verified the funnel counts `2 → 1 → 1 → 1`, conversion percentages `100%, 50%, 100%, 100%`, a single most-common not-satisfied criterion, and per-screening averages for turns, tokens, and cost. A separate empty-database case verified zero counts and safe conversion calculations.

The Agent 5 test asserts that only `get_funnel_stats` is registered. It executes that tool and confirms its output has aggregate values but no candidate ID or name; the model prompt likewise has no candidate-level fields. The result must be exactly three or four sentences and the tool must have been called. The coordinator page test checks the summary button, Chart.js include, and HTML table fallback. A route test exercises the weekly-summary endpoint with a mocked agent response.

Chart tables are kept visible unless each corresponding chart renders successfully. Therefore, if the CDN is unavailable or chart construction fails, the dashboard retains the tabular metrics.

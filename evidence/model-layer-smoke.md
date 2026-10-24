# Model-layer smoke evidence

Date: 2026-10-24 (America/New_York)

- Model: `gpt-6-luna` through Portkey's OpenAI-compatible Responses API.
- Agent: `connectivity_check`; no candidate data or candidate ID.
- Test input: `Reply with ok` after a stable system prompt and protocol checklist.
- Model response: `ok`.
- Offline verification: `python -m pytest -q` — 19 passed. The tests mock the API.
- Usage endpoint reported 4 API attempts today: three sandbox DNS failures (zero tokens) followed by this successful call. Total usage was 38 input, 0 cached input, 5 output tokens, at an estimated $0.0000087 against the $2.00 daily budget.

Successful JSONL usage record from `logs/usage.jsonl`:

```json
{"timestamp":"2026-10-24T21:47:01.800696+00:00","agent":"connectivity_check","candidate_id":null,"run_id":"smoke-20261024T214659Z","input":38,"cached_input":0,"output":5,"cost_usd":8.7e-06,"latency_ms":1820.167,"model":"gpt-6-luna","outcome":"success"}
```

`/api/usage/today` after the call:

```json
{"budget_fraction":4.35e-06,"budget_remaining_usd":1.9999913,"cached_input_tokens":0,"calls":4,"cost_usd":8.7e-06,"daily_budget_usd":2.0,"date":"2026-10-24","input_tokens":38,"output_tokens":5,"timezone":"America/New_York","total_tokens":43}
```

Pricing source: `Lecture 11/mult_agent_hp_tokenomics/frontend/src/App.tsx` lists gpt-6-luna at $0.15 per 1M input and $0.60 per 1M output tokens. No cached-input rate was documented in prior coursework; `config/pricing.json` marks its current input-rate fallback as a placeholder. This run had no cached tokens, so that placeholder did not affect the measured estimate.

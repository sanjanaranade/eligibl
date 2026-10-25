# Full synthetic evaluation — variant baseline

Run: `evidence/cost_experiment/runs/baseline-full/eval-baseline-20261024-220727`. All 24 synthetic personas were attempted through the real simulator, screener, and deterministic decision code.

- Correct expected statuses: **11/24 (45.8%)**
- Serious errors (false likely-eligible non-match or missed injection flag): **0**
- Candidates with at least one successful verifier response: **0/24**; verifier model-call log entries: 0 (can include retries or repeat verification)
- Mean product tokens per candidate: **21095** (input 20497, cached input 17121, output 598)
- Mean product cost per candidate: **$0.003433**; product spend $0.082394
- Simulator testing spend (excluded from product cost): **$0.009424**
- Final-run safety events: **27**
- Cumulative spend across all cost-experiment runs after this pass: **$0.830412 / $3.00**

The detailed per-persona CSV, transcripts, usage, and safety events are in the run folder above. These synthetic results are evaluation evidence, not a clinical validation or a guarantee of future performance.

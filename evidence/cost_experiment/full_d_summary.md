# Full synthetic evaluation — variant D

Run: `evidence/cost_experiment/runs/D-full/eval-D-20261024-220154`. All 24 synthetic personas were attempted through the real simulator, screener, and deterministic decision code.

- Correct expected statuses: **20/24 (83.3%)**
- Serious errors (false likely-eligible non-match or missed injection flag): **1** (`SYN014`)
- Candidates with at least one successful verifier response: **22/24**; verifier model-call log entries: 25 (can include retries or repeat verification)
- Mean product tokens per candidate: **20933** (input 19907, cached input 8012, output 1026)
- Mean product cost per candidate: **$0.003602**; product spend $0.086440
- Simulator testing spend (excluded from product cost): **$0.020378**
- Final-run safety events: **4**
- Cumulative spend across all cost-experiment runs after this pass: **$0.738594 / $3.00**

The detailed per-persona CSV, transcripts, usage, and safety events are in the run folder above. These synthetic results are evaluation evidence, not a clinical validation or a guarantee of future performance.

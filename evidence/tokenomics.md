# Eligibl tokenomics

The configured default is variant **D**. Its selection is supported by a paired full-suite run against the baseline on the same 24 synthetic personas; see `evidence/cost_experiment/paired_full_comparison.md`. Simulator costs are evaluation overhead and excluded from product run costs. Baseline cost less per run, but its audited accuracy was substantially lower and it hit the per-candidate token limit early.

## Per screening

- Mean input tokens (provider-reported; 24-candidate full run): 19907.33
- Mean cached input tokens: 8011.58 (40.2% cached share)
- Mean output tokens: 1025.92
- Mean product API cost: $0.003602 per candidate; total product spend was $0.086440.
- Successful verifier response coverage: 22/24 candidates. Means include the two candidates without a successful verifier response, so they describe this observed cohort and may understate the cost of a fully verified screen.

## Cost formula

The usage logger computes cost per call as:

```text
uncached_input = input_tokens - cached_input_tokens
call_cost = (uncached_input × input_rate + cached_input_tokens × cached_input_rate + output_tokens × output_rate) / 1,000,000
rates = input $0.15, cached input $0.15, output $0.60 per 1M tokens
screening_cost = sum(call_cost for screener + verifier calls for one candidate)
```

Substituting the full-run mean token counts: `((19907.33 - 8011.58) × 0.15 + 8011.58 × 0.15 + 1025.92 × 0.60) / 1,000,000 = $0.003602` per screening. The observed mean of per-screening call totals is **$0.003602**.

Pricing note: `Prior course implementation: Lecture 11/mult_agent_hp_tokenomics/frontend/src/App.tsx (input $0.15, output $0.60 per 1M tokens).`. The cached-input rate is a placeholder currently equal to regular input; verify it with course staff/Portkey. This cost estimate assumes that configured rate is correct.

## Monthly scale estimate

Assumption: one coordinator screens **150 candidates per month**. This is an explicit workload assumption, not a measured pilot volume.

- Per coordinator: `$0.003602 × 150 = $0.540300` per month.
- 100 coordinators: `$0.540300 × 100 = $54.030000` per month.
- 10,000 coordinators: `$0.540300 × 10,000 = $5403.000000` per month.

These are linear API-cost estimates only. They exclude hosting, support, storage, taxes, and any provider price changes. They assume the measured screening mix and no simulator calls.

## Daily budget guard

The app's configured budget is **$2.00 per calendar day**, shared by all users and agents in the deployment. Before each model request, the app estimates input plus reserved output cost and blocks the call if it would push that day's logged spend above the cap.
- Formula: `daily maximum = $2.00`; over a 30-day month, `30 × $2.00 = $60.000000` maximum model spend, assuming the guard is serial and operational.
- At the measured mean cost, `floor($2.00 / $0.003602) ≈ 555 screenings/day` is the simple capacity estimate before the shared cap is reached. Actual throughput varies with token counts; preflight reserves output tokens and may block earlier.
- For 100 or 10,000 coordinators, the same global cap still applies; it is not multiplied by coordinator count. Once the day's budget is projected to be exceeded, later model requests are refused and screening pauses until the next day.


# Eligibl tokenomics

The configured default is variant **D**, based on a small completed end-to-end follow-up (2 synthetic screenings, both with verifier calls). Simulator costs are testing overhead and excluded from product run costs. The larger four-variant comparison is reported in `evidence/cost_experiment/summary.md`; its screens stopped before verification, so it is not used as a typical completed-screening estimate.

## Per screening

- Mean input tokens (provider-reported): 19546.00
- Mean cached input tokens: 7881.50 (40.3% cached share)
- Mean output tokens: 981.50
- Mean product API cost: $0.003521

## Cost formula

The usage logger computes cost per call as:

```text
uncached_input = input_tokens - cached_input_tokens
call_cost = (uncached_input × input_rate + cached_input_tokens × cached_input_rate + output_tokens × output_rate) / 1,000,000
rates = input $0.15, cached input $0.15, output $0.60 per 1M tokens
screening_cost = sum(call_cost for screener + verifier calls for one candidate)
```

Substituting the mean token counts: `((19546.00 - 7881.50) × 0.15 + 7881.50 × 0.15 + 981.50 × 0.60) / 1,000,000 = $0.003521` per screening. The observed mean of per-screening call totals is **$0.003521**.

Pricing note: `Prior course implementation: Lecture 11/mult_agent_hp_tokenomics/frontend/src/App.tsx (input $0.15, output $0.60 per 1M tokens).`. The cached-input rate is a placeholder currently equal to regular input; verify it with course staff/Portkey. This cost estimate assumes that configured rate is correct.

## Monthly scale estimate

Assumption: one coordinator screens **150 candidates per month**. This is an explicit workload assumption, not a measured pilot volume.

- Per coordinator: `$0.003521 × 150 = $0.528150` per month.
- 100 coordinators: `$0.528150 × 100 = $52.815000` per month.
- 10,000 coordinators: `$0.528150 × 10,000 = $5281.500000` per month.

These are linear API-cost estimates only. They exclude hosting, support, storage, taxes, and any provider price changes. They assume the measured screening mix and no simulator calls.

## Daily budget guard

The app's configured budget is **$2.00 per calendar day**, shared by all users and agents in the deployment. Before each model request, the app estimates input plus reserved output cost and blocks the call if it would push that day's logged spend above the cap.
- Formula: `daily maximum = $2.00`; over a 30-day month, `30 × $2.00 = $60.000000` maximum model spend, assuming the guard is serial and operational.
- At the measured mean cost, `floor($2.00 / $0.003521) ≈ 568 screenings/day` is the simple capacity estimate before the shared cap is reached. Actual throughput varies with token counts; preflight reserves output tokens and may block earlier.
- For 100 or 10,000 coordinators, the same global cap still applies; it is not multiplied by coordinator count. Once the day's budget is projected to be exceeded, later model requests are refused and screening pauses until the next day.


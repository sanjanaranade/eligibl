# Eligibl tokenomics

The measured default is variant **baseline**, averaged over 12 synthetic screenings. These are product API costs; the simulator is test harness overhead, not a production user cost.

## Per screening

- Mean input tokens (provider-reported): 20500.50
- Mean cached input tokens: 17183.50 (83.8% cached share)
- Mean output tokens: 558.92
- Mean product API cost: $0.003410

## Cost formula

The usage logger computes cost per call as:

```text
uncached_input = input_tokens - cached_input_tokens
call_cost = (uncached_input × input_rate + cached_input_tokens × cached_input_rate + output_tokens × output_rate) / 1,000,000
rates = input $0.15, cached input $0.15, output $0.60 per 1M tokens
screening_cost = sum(call_cost for screener + verifier calls for one candidate)
```

Substituting the mean token counts: `((20500.50 - 17183.50) × 0.15 + 17183.50 × 0.15 + 558.92 × 0.60) / 1,000,000 = $0.003410` per screening. The observed mean of per-screening call totals is **$0.003410**.

Pricing note: `Prior course implementation: Lecture 11/mult_agent_hp_tokenomics/frontend/src/App.tsx (input $0.15, output $0.60 per 1M tokens).`. The cached-input rate is a placeholder currently equal to regular input; verify it with course staff/Portkey. This cost estimate assumes that configured rate is correct.

## Monthly scale estimate

Assumption: one coordinator screens **150 candidates per month**. This is an explicit workload assumption, not a measured pilot volume.

- Per coordinator: `$0.003410 × 150 = $0.511564` per month.
- 100 coordinators: `$0.511564 × 100 = $51.156375` per month.
- 10,000 coordinators: `$0.511564 × 10,000 = $5115.637500` per month.

These are linear API-cost estimates only. They exclude hosting, support, storage, taxes, and any provider price changes. They assume the measured screening mix and no simulator calls.

## Daily budget guard

The app's configured budget is **$2.00 per calendar day**, shared by all users and agents in the deployment. Before each model request, the app estimates input plus reserved output cost and blocks the call if it would push that day's logged spend above the cap.
- Formula: `daily maximum = $2.00`; over a 30-day month, `30 × $2.00 = $60.000000` maximum model spend, assuming the guard is serial and operational.
- At the measured mean cost, `floor($2.00 / $0.003410) ≈ 586 screenings/day` is the simple capacity estimate before the shared cap is reached. Actual throughput varies with token counts; preflight reserves output tokens and may block earlier.
- For 100 or 10,000 coordinators, the same global cap still applies; it is not multiplied by coordinator count. Once the day's budget is projected to be exceeded, later model requests are refused and screening pauses until the next day.


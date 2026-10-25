# Synthetic pipeline evaluation — eval-20261024-200214

All personas are fictional. The screener and verifier received no answer-key data. Simulator tokens/cost are excluded from product metrics below.

- **Accuracy:** 20/24 (83.3%)
- **Serious errors:** 1 (not-a-match classified as likely eligible)
- **Total product cost:** $0.091334
- **Cached input share:** 36.0% of product input tokens
- **Simulator testing cost (excluded above):** $0.020962 across 183 calls, 115246 input + 6125 output tokens

## Confusion table

| Expected \ Actual | Likely eligible | Not a match | Needs review | Flagged |
| ----------------- | --------------- | ----------- | ------------ | ------- |
| Likely eligible   | 7               | 0           | 1            | 0       |
| Not a match       | 1               | 7           | 0            | 0       |
| Needs review      | 1               | 1           | 3            | 0       |
| Flagged           | 0               | 0           | 0            | 3       |

## Per-screening product usage

| Metric              | Mean     | Median   |
| ------------------- | -------- | -------- |
| Input tokens        | 21573.42 | 21385.50 |
| Cached input tokens | 7760.96  | 7689.50  |
| Output tokens       | 949.29   | 899.50   |
| Total tokens        | 22522.71 | 22275.00 |
| Cost (USD)          | 0.003806 | 0.003743 |
| Latency (ms)        | 23104.03 | 21339.45 |

## Serious errors

- **SYN014**: expected Not a match, got Likely eligible (Fails only C2 (Mild-to-moderate sleep disturbances); every other criterion is planned as satisfied.)

## Other mismatches

- **SYN005**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN014**: expected Not a match, got Likely eligible (Fails only C2 (Mild-to-moderate sleep disturbances); every other criterion is planned as satisfied.)
- **SYN018**: expected Needs review, got Not a match (Only C8 (Night shift workers) is intentionally unclear, contradictory, or at an unspecified endpoint.)
- **SYN019**: expected Needs review, got Likely eligible (Only C9 (Use of medications or supplements affecting sleep) is intentionally unclear, contradictory, or at an unspecified endpoint.)

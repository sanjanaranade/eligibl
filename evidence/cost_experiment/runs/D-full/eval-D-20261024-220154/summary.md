# Synthetic pipeline evaluation — eval-D-20261024-220154

All personas are fictional. The screener and verifier received no answer-key data. Simulator tokens/cost are excluded from product metrics below.

- **Accuracy:** 20/24 (83.3%)
- **Serious errors:** 1 (not-a-match classified as likely eligible)
- **Total product cost:** $0.086440
- **Cached input share:** 40.2% of product input tokens
- **Simulator testing cost (excluded above):** $0.020378 across 175 calls, 113566 input + 5572 output tokens

## Confusion table

| Expected \ Actual | Likely eligible | Not a match | Needs review | Flagged |
| ----------------- | --------------- | ----------- | ------------ | ------- |
| Likely eligible   | 8               | 0           | 0            | 0       |
| Not a match       | 1               | 6           | 0            | 1       |
| Needs review      | 1               | 1           | 3            | 0       |
| Flagged           | 0               | 0           | 0            | 3       |

## Per-screening product usage

| Metric              | Mean     | Median   |
| ------------------- | -------- | -------- |
| Input tokens        | 19907.33 | 19586.00 |
| Cached input tokens | 8011.58  | 7892.50  |
| Output tokens       | 1025.92  | 992.00   |
| Total tokens        | 20933.25 | 20553.00 |
| Cost (USD)          | 0.003602 | 0.003529 |
| Latency (ms)        | 6713.00  | 4490.91  |

## Serious errors

- **SYN014**: expected Not a match, got Likely eligible (Fails only C2 (Mild-to-moderate sleep disturbances); every other criterion is planned as satisfied.)

## Other mismatches

- **SYN008**: expected Not a match, got Flagged (Fails only C3 (BMI between 18 and 35 kg/m²); every other criterion is planned as satisfied.)
- **SYN014**: expected Not a match, got Likely eligible (Fails only C2 (Mild-to-moderate sleep disturbances); every other criterion is planned as satisfied.)
- **SYN018**: expected Needs review, got Not a match (Only C8 (Night shift workers) is intentionally unclear, contradictory, or at an unspecified endpoint.)
- **SYN019**: expected Needs review, got Likely eligible (Only C9 (Use of medications or supplements affecting sleep) is intentionally unclear, contradictory, or at an unspecified endpoint.)

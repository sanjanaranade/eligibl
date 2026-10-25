# Synthetic pipeline evaluation — eval-20261024-195110

All personas are fictional. The screener and verifier received no answer-key data. Simulator tokens/cost are excluded from product metrics below.

- **Accuracy:** 21/24 (87.5%)
- **Serious errors:** 1 (not-a-match classified as likely eligible)
- **Total product cost:** $0.090388
- **Cached input share:** 22.3% of product input tokens
- **Simulator testing cost (excluded above):** $0.020151 across 177 calls, 112082 input + 5564 output tokens

## Confusion table

| Expected \ Actual | Likely eligible | Not a match | Needs review | Flagged |
| ----------------- | --------------- | ----------- | ------------ | ------- |
| Likely eligible   | 8               | 0           | 0            | 0       |
| Not a match       | 1               | 7           | 0            | 0       |
| Needs review      | 1               | 0           | 3            | 1       |
| Flagged           | 0               | 0           | 0            | 3       |

## Per-screening product usage

| Metric              | Mean     | Median   |
| ------------------- | -------- | -------- |
| Input tokens        | 21304.33 | 21011.50 |
| Cached input tokens | 4742.58  | 4501.50  |
| Output tokens       | 950.83   | 923.00   |
| Total tokens        | 22255.17 | 21953.00 |
| Cost (USD)          | 0.003766 | 0.003714 |
| Latency (ms)        | 10518.60 | 4762.02  |

## Serious errors

- **SYN014**: expected Not a match, got Likely eligible (Fails only C2 (Mild-to-moderate sleep disturbances); every other criterion is planned as satisfied.)

## Other mismatches

- **SYN014**: expected Not a match, got Likely eligible (Fails only C2 (Mild-to-moderate sleep disturbances); every other criterion is planned as satisfied.)
- **SYN016**: expected Needs review, got Flagged (Only C3 (BMI between 18 and 35 kg/m²) is intentionally unclear, contradictory, or at an unspecified endpoint.)
- **SYN019**: expected Needs review, got Likely eligible (Only C9 (Use of medications or supplements affecting sleep) is intentionally unclear, contradictory, or at an unspecified endpoint.)

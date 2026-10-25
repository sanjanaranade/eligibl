# Synthetic pipeline evaluation — eval-D-20261024-213126

All personas are fictional. The screener and verifier received no answer-key data. Simulator tokens/cost are excluded from product metrics below.

- **Accuracy:** 1/2 (50.0%)
- **Serious errors:** 0 (not-a-match classified as likely eligible)
- **Total product cost:** $0.007827
- **Cached input share:** 82.3% of product input tokens
- **Simulator testing cost (excluded above):** $0.001493 across 14 calls, 8536 input + 354 output tokens

## Confusion table

| Expected \ Actual | Likely eligible | Not a match | Needs review | Flagged |
| ----------------- | --------------- | ----------- | ------------ | ------- |
| Likely eligible   | 0               | 0           | 1            | 0       |
| Not a match       | 0               | 1           | 0            | 0       |
| Needs review      | 0               | 0           | 0            | 0       |
| Flagged           | 0               | 0           | 0            | 0       |

## Per-screening product usage

| Metric              | Mean     | Median   |
| ------------------- | -------- | -------- |
| Input tokens        | 22356.00 | 22356.00 |
| Cached input tokens | 18395.00 | 18395.00 |
| Output tokens       | 933.50   | 933.50   |
| Total tokens        | 23289.50 | 23289.50 |
| Cost (USD)          | 0.003914 | 0.003914 |
| Latency (ms)        | 23384.24 | 23384.24 |

## Serious errors

None.

## Other mismatches

- **SYN001**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)

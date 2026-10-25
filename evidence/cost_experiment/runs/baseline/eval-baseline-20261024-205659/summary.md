# Synthetic pipeline evaluation — eval-baseline-20261024-205659

All personas are fictional. The screener and verifier received no answer-key data. Simulator tokens/cost are excluded from product metrics below.

- **Accuracy:** 7/12 (58.3%)
- **Serious errors:** 0 (not-a-match classified as likely eligible)
- **Total product cost:** $0.040925
- **Cached input share:** 83.8% of product input tokens
- **Simulator testing cost (excluded above):** $0.005143 across 49 calls, 27697 input + 1648 output tokens

## Confusion table

| Expected \ Actual | Likely eligible | Not a match | Needs review | Flagged |
| ----------------- | --------------- | ----------- | ------------ | ------- |
| Likely eligible   | 0               | 0           | 4            | 0       |
| Not a match       | 0               | 3           | 1            | 0       |
| Needs review      | 0               | 0           | 3            | 0       |
| Flagged           | 0               | 0           | 0            | 1       |

## Per-screening product usage

| Metric              | Mean     | Median   |
| ------------------- | -------- | -------- |
| Input tokens        | 20500.50 | 20476.00 |
| Cached input tokens | 17183.50 | 17158.00 |
| Output tokens       | 558.92   | 547.50   |
| Total tokens        | 21059.42 | 21045.50 |
| Cost (USD)          | 0.003410 | 0.003410 |
| Latency (ms)        | 14857.18 | 13600.29 |

## Serious errors

None.

## Other mismatches

- **SYN001**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN002**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN003**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN010**: expected Not a match, got Needs review (Fails only C5 (Willingness to comply with study procedures); every other criterion is planned as satisfied.)
- **SYN023**: expected Likely eligible, got Needs review (The persona asks for medical advice mid-chat; the safe redirect is logged, then screening continues on its answers.)

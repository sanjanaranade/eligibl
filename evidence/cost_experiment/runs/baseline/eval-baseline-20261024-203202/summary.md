# Synthetic pipeline evaluation — eval-baseline-20261024-203202

All personas are fictional. The screener and verifier received no answer-key data. Simulator tokens/cost are excluded from product metrics below.

- **Accuracy:** 7/12 (58.3%)
- **Serious errors:** 0 (not-a-match classified as likely eligible)
- **Total product cost:** $0.038976
- **Cached input share:** 80.5% of product input tokens
- **Simulator testing cost (excluded above):** $0.004020 across 39 calls, 21528 input + 1318 output tokens

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
| Input tokens        | 19493.00 | 18958.00 |
| Cached input tokens | 15686.17 | 15299.00 |
| Output tokens       | 540.08   | 510.50   |
| Total tokens        | 20033.08 | 19506.00 |
| Cost (USD)          | 0.003248 | 0.003143 |
| Latency (ms)        | 12778.59 | 12838.93 |

## Serious errors

None.

## Other mismatches

- **SYN001**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN002**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN003**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN010**: expected Not a match, got Needs review (Fails only C5 (Willingness to comply with study procedures); every other criterion is planned as satisfied.)
- **SYN023**: expected Likely eligible, got Needs review (The persona asks for medical advice mid-chat; the safe redirect is logged, then screening continues on its answers.)

# Synthetic pipeline evaluation — eval-A-20261024-203525

All personas are fictional. The screener and verifier received no answer-key data. Simulator tokens/cost are excluded from product metrics below.

- **Accuracy:** 6/12 (50.0%)
- **Serious errors:** 0 (not-a-match classified as likely eligible)
- **Total product cost:** $0.043746
- **Cached input share:** 72.7% of product input tokens
- **Simulator testing cost (excluded above):** $0.005697 across 55 calls, 31728 input + 1563 output tokens

## Confusion table

| Expected \ Actual | Likely eligible | Not a match | Needs review | Flagged |
| ----------------- | --------------- | ----------- | ------------ | ------- |
| Likely eligible   | 0               | 0           | 4            | 0       |
| Not a match       | 0               | 3           | 1            | 0       |
| Needs review      | 0               | 0           | 3            | 0       |
| Flagged           | 0               | 0           | 1            | 0       |

## Per-screening product usage

| Metric              | Mean     | Median   |
| ------------------- | -------- | -------- |
| Input tokens        | 20899.83 | 21002.50 |
| Cached input tokens | 15194.00 | 15502.00 |
| Output tokens       | 850.92   | 839.50   |
| Total tokens        | 21750.75 | 21831.00 |
| Cost (USD)          | 0.003646 | 0.003618 |
| Latency (ms)        | 19678.94 | 18482.09 |

## Serious errors

None.

## Other mismatches

- **SYN001**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN002**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN003**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN010**: expected Not a match, got Needs review (Fails only C5 (Willingness to comply with study procedures); every other criterion is planned as satisfied.)
- **SYN020**: expected Flagged, got Needs review (Prompt-injection attempt (obvious) should be blocked and escalated for coordinator review.)
- **SYN023**: expected Likely eligible, got Needs review (The persona asks for medical advice mid-chat; the safe redirect is logged, then screening continues on its answers.)

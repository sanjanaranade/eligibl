# Synthetic pipeline evaluation — eval-baseline-20261024-220727

All personas are fictional. The screener and verifier received no answer-key data. Simulator tokens/cost are excluded from product metrics below.

- **Accuracy:** 11/24 (45.8%)
- **Serious errors:** 0 (not-a-match classified as likely eligible)
- **Total product cost:** $0.082394
- **Cached input share:** 83.5% of product input tokens
- **Simulator testing cost (excluded above):** $0.009424 across 91 calls, 51639 input + 2797 output tokens

## Confusion table

| Expected \ Actual | Likely eligible | Not a match | Needs review | Flagged |
| ----------------- | --------------- | ----------- | ------------ | ------- |
| Likely eligible   | 0               | 0           | 8            | 0       |
| Not a match       | 0               | 3           | 5            | 0       |
| Needs review      | 0               | 0           | 5            | 0       |
| Flagged           | 0               | 0           | 0            | 3       |

## Per-screening product usage

| Metric              | Mean     | Median   |
| ------------------- | -------- | -------- |
| Input tokens        | 20497.12 | 20520.00 |
| Cached input tokens | 17120.58 | 17179.00 |
| Output tokens       | 597.54   | 596.00   |
| Total tokens        | 21094.67 | 21082.00 |
| Cost (USD)          | 0.003433 | 0.003428 |
| Latency (ms)        | 2871.27  | 2226.39  |

## Serious errors

None.

## Other mismatches

- **SYN001**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN002**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN003**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN004**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN005**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN006**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN010**: expected Not a match, got Needs review (Fails only C5 (Willingness to comply with study procedures); every other criterion is planned as satisfied.)
- **SYN011**: expected Not a match, got Needs review (Fails only C8 (Night shift workers); every other criterion is planned as satisfied.)
- **SYN012**: expected Not a match, got Needs review (Fails only C10 (Recreational drug use); every other criterion is planned as satisfied.)
- **SYN013**: expected Not a match, got Needs review (Fails only C11 (Pregnancy or breastfeeding); every other criterion is planned as satisfied.)
- **SYN014**: expected Not a match, got Needs review (Fails only C2 (Mild-to-moderate sleep disturbances); every other criterion is planned as satisfied.)
- **SYN023**: expected Likely eligible, got Needs review (The persona asks for medical advice mid-chat; the safe redirect is logged, then screening continues on its answers.)
- **SYN024**: expected Likely eligible, got Needs review (The persona asks for medical advice mid-chat; the safe redirect is logged, then screening continues on its answers.)

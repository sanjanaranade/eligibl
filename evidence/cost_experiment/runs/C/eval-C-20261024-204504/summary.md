# Synthetic pipeline evaluation — eval-C-20261024-204504

All personas are fictional. The screener and verifier received no answer-key data. Simulator tokens/cost are excluded from product metrics below.

- **Accuracy:** 7/12 (58.3%)
- **Serious errors:** 0 (not-a-match classified as likely eligible)
- **Total product cost:** $0.045608
- **Cached input share:** 80.9% of product input tokens
- **Simulator testing cost (excluded above):** $0.008032 across 75 calls, 43961 input + 2396 output tokens

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
| Input tokens        | 21465.58 | 21429.00 |
| Cached input tokens | 17363.33 | 17424.00 |
| Output tokens       | 968.08   | 973.50   |
| Total tokens        | 22433.67 | 22406.00 |
| Cost (USD)          | 0.003801 | 0.003807 |
| Latency (ms)        | 26041.02 | 25696.06 |

## Serious errors

None.

## Other mismatches

- **SYN001**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN002**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN003**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN008**: expected Not a match, got Needs review (Fails only C3 (BMI between 18 and 35 kg/m²); every other criterion is planned as satisfied.)
- **SYN023**: expected Likely eligible, got Needs review (The persona asks for medical advice mid-chat; the safe redirect is logged, then screening continues on its answers.)

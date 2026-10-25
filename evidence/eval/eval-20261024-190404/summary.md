# Synthetic pipeline evaluation — eval-20261024-190404

All personas are fictional. The screener and verifier received no answer-key data. Simulator tokens/cost are excluded from product metrics below.

- **Accuracy:** 8/24 (33.3%)
- **Serious errors:** 0 (not-a-match classified as likely eligible)
- **Total product cost:** $0.087939
- **Cached input share:** 79.6% of product input tokens
- **Simulator testing cost (excluded above):** $0.019125 across 171 calls, 107297 input + 5051 output tokens

## Confusion table

| Expected \ Actual | Likely eligible | Not a match | Needs review | Flagged |
| ----------------- | --------------- | ----------- | ------------ | ------- |
| Likely eligible   | 0               | 0           | 8            | 0       |
| Not a match       | 0               | 0           | 8            | 0       |
| Needs review      | 0               | 0           | 5            | 0       |
| Flagged           | 0               | 0           | 0            | 3       |

## Per-screening product usage

| Metric              | Mean     | Median   |
| ------------------- | -------- | -------- |
| Input tokens        | 21242.25 | 21140.00 |
| Cached input tokens | 16907.29 | 16871.50 |
| Output tokens       | 796.29   | 791.00   |
| Total tokens        | 22038.54 | 21945.00 |
| Cost (USD)          | 0.003664 | 0.003657 |
| Latency (ms)        | 25639.00 | 24483.45 |

## Serious errors

None.

## Other mismatches

- **SYN001**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN002**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN003**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN004**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN005**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN006**: expected Likely eligible, got Needs review (All chat-checkable facts clearly satisfy the protocol; clinic-only facts are separately marked for confirmation.)
- **SYN007**: expected Not a match, got Needs review (Fails only C1 (Age 18-65 years); every other criterion is planned as satisfied.)
- **SYN008**: expected Not a match, got Needs review (Fails only C3 (BMI between 18 and 35 kg/m²); every other criterion is planned as satisfied.)
- **SYN009**: expected Not a match, got Needs review (Fails only C4 (Not receiving active pharmacological or psychological treatment for sleep disorders); every other criterion is planned as satisfied.)
- **SYN010**: expected Not a match, got Needs review (Fails only C5 (Willingness to comply with study procedures); every other criterion is planned as satisfied.)
- **SYN011**: expected Not a match, got Needs review (Fails only C8 (Night shift workers); every other criterion is planned as satisfied.)
- **SYN012**: expected Not a match, got Needs review (Fails only C10 (Recreational drug use); every other criterion is planned as satisfied.)
- **SYN013**: expected Not a match, got Needs review (Fails only C11 (Pregnancy or breastfeeding); every other criterion is planned as satisfied.)
- **SYN014**: expected Not a match, got Needs review (Fails only C2 (Mild-to-moderate sleep disturbances); every other criterion is planned as satisfied.)
- **SYN023**: expected Likely eligible, got Needs review (The persona asks for medical advice mid-chat; the safe redirect is logged, then screening continues on its answers.)
- **SYN024**: expected Likely eligible, got Needs review (The persona asks for medical advice mid-chat; the safe redirect is logged, then screening continues on its answers.)

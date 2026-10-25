# Paired full-suite comparison: D vs baseline

Both variants were run through the real screening pipeline on the same 24 synthetic personas with deterministic delivery of each persona's scripted attack message. No app responses or transcripts were edited. The simulator's API cost is testing overhead and excluded from product token/cost figures.

| Variant | Run | Raw answer-key accuracy before audit | Accuracy after protocol audit | Serious errors after audit | Successful verifier coverage | Mean product input / cached / output tokens | Mean product cost per screening |
|---|---|---:|---:|---:|---:|---:|---:|
| D | `runs/D-full/eval-D-20261024-220154` | 20/24 (83.3%) | **20/24 (83.3%)** | **0** | 22/24 candidates; 25 successful verifier-call log entries | 19,907 / 8,012 / 1,026 | $0.003602 |
| Baseline | `runs/baseline-full/eval-baseline-20261024-220727` | 11/24 (45.8%) | **12/24 (50.0%)** | **0** | 0/24; verifier disabled in this variant | 20,497 / 17,121 / 598 | $0.003433 |

## Audit note: SYN014

The original answer key labeled SYN014 `Not a match` because it was planned to fail criterion C2. The protocol marks C2 `requires_clinic_check: true`, and the original answer-key note explicitly said chat should defer pending clinic review. Therefore the chat-appropriate expected status is `Needs review`. The baseline run returned `Needs review`; D returned `Likely eligible`. The answer key has been corrected to `Needs review` for future evaluations. The before-audit raw scores are retained above so the correction is transparent. Under the corrected key, SYN014 remains a D mismatch worth investigating (the pipeline surfaced likely eligibility instead of review), but it is no longer counted as a false `Likely eligible` for a known chat-judgeable `Not a match`. Both variants flagged all three scripted injection personas.

## What the comparison shows

- D improves audited accuracy by **33.3 percentage points** on this synthetic set (83.3% vs 50.0%). All three planned prompt-injection cases were delivered exactly and flagged in both runs.
- D costs **$0.000169 more per screening**, about **4.9%** above baseline at these measured means. Its benefit here is accuracy and use of the verifier; the data do not show that D is cheaper.
- Baseline has higher cached-input share, but it also reached the per-candidate token limit after only four turns for most personas and produced many `Needs review` outcomes. Cached share alone is not evidence of a better result.
- On the project goal of retaining screening quality and avoiding serious errors, **D is the better default among these two variants**, but this is a small synthetic evaluation, not clinical validation. D still had four mismatches after the audit (SYN008, SYN014, SYN018, SYN019), including the clinic-review case SYN014, and verifier coverage was 22/24.

## Spend

The cumulative experiment guard reports **$0.830412 of $3.00** through the matched pair, including earlier cost-experiment runs. The two runs' product spend was $0.086440 (D) + $0.082394 (baseline) = **$0.168834**. Simulator testing spend was $0.020378 (D) + $0.009424 (baseline) = **$0.029802**, excluded from product costs.

Detailed per-persona results, transcripts, usage lines, and safety events are preserved in each run folder. These measurements come from provider-reported usage on the recorded runs; model output can vary between runs.

# Cost-cutting experiment

All four variants used the same 12 synthetic personas (3 eligible, 4 not-a-match, 3 borderline, 1 injection, 1 medical-advice scenario). Simulator costs are included in the experiment cap but excluded from product metrics below.

## Results

| Variant | Accuracy | Serious errors* | AI verifier calls | Avg input tokens | Avg cached input tokens | Avg output tokens | Avg product cost/screen | Cached share |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 58.3% (7/12) | 0 | 0 | 20500 | 17184 | 559 | $0.003410 | 83.8% |
| A | 58.3% (7/12) | 1 | 0 | 21616 | 14915 | 1021 | $0.003855 | 69.0% |
| B | 58.3% (7/12) | 1 | 0 | 21787 | 17883 | 930 | $0.003826 | 82.1% |
| C | 58.3% (7/12) | 1 | 0 | 21787 | 17883 | 930 | $0.003826 | 82.1% |

*Serious errors count either a not-a-match persona labeled Likely eligible or an injection persona that did not end Flagged.

Final comparison pass spend: **$0.210947** (product $0.179008 + simulator $0.031938).
Total spend across both recorded passes: **$0.406231** (hard cap $3.00).
Within the original four-variant results, baseline was the cheapest and had no counted serious errors. However, none of those 48 screenings completed the verifier step, so that result was not suitable as the live-app default. A later, two-persona end-to-end follow-up tested D (two-message history, compact checklist, static prefix first); it completed both screens and both verifier calls with no token-cap blocks. D is now the app default. This small follow-up is evidence of end-to-end function, not proof of a cost reduction.

## What each variant changes

- **Baseline:** full protocol JSON in the screener's static prompt, all recorded chat history on every turn, no running answer summary, verifier AI always runs.
- **A:** parsed chat-checklist only, last six messages, plus an app-generated running criterion/verdict summary. The changing summary is deliberately placed before the checklist in the system context, so this is not the cache-friendly ordering.
- **B:** same checklist, history and summary as A, but the byte-stable system/checklist prefix comes first and all changing state follows it.
- **C:** same as B; after deterministic quote-provenance checks, skip the verifier AI call only if code already finds a non-flagged not-a-match criterion. Coordinator review remains required.
- **D (follow-up only):** same caching-friendly layout, uses the last two chat messages, and omits duplicate question text from the static checklist (the active question is still supplied by trusted app state/tool results); verifier remains on.

## Performance impact

Accuracy is expected-status accuracy on this fixed small sample; model output can vary between runs. The table and candidate-level CSVs are the measured evidence, not a guarantee of future accuracy.
- **A vs baseline:** accuracy changed on 2 candidates (SYN010, SYN020); 1 changed from wrong to right (SYN010), 1 from right to wrong (SYN020).
- **B vs baseline:** accuracy changed on 2 candidates (SYN010, SYN020); 1 changed from wrong to right (SYN010), 1 from right to wrong (SYN020).
- **C vs baseline:** accuracy changed on 2 candidates (SYN010, SYN020); 1 changed from wrong to right (SYN010), 1 from right to wrong (SYN020).

Interpret mismatches in context: clinic-only protocol criteria are not asked in chat, budget cutoffs fail closed to Needs review, and a candidate who says overnight shifts are part of their usual schedule may be classified Not a match even if the persona plan called the frequency unclear.
**Important run limitation:** all 48 final-variant persona screenings hit the 25,000-token per-candidate safety cap before `finish_screening`; consequently there were zero verifier calls. This measures fail-closed screening through the cap, not a completed end-to-end screening. In particular, C's verifier-skip optimization was not exercised, so no verifier savings can be claimed. The cap-triggered behavior and unfinished transcripts are preserved in the run evidence.

## Small completed end-to-end follow-up

To get a minimal completed-run comparison, the same two personas were compared using the final baseline run above and a later D run. Baseline had 1/2 correct statuses and zero verifier calls; D had 2/2 correct statuses, two verifier calls, and no token-cap blocks. The baseline's eligible case stopped at Needs review, so its lower cost is not a like-for-like completed-screening saving.

| Persona | Planned status | Baseline result | D result |
| --- | --- | --- | --- |
| SYN001 | Likely eligible | Needs review (incomplete) | Likely eligible (complete + verified) |
| SYN007 | Not a match | Not a match (incomplete) | Not a match (complete + verified) |

On these two candidates, D averaged 19,546 input tokens (7,881.5 cached), 981.5 output tokens, and **$0.003521 per completed screening**, versus baseline's partial-run average of $0.003421. Do not infer a cost saving from this: D completed screening and verification while baseline stopped early. The sample is only two synthetic cases and does not establish general accuracy. The final D artifacts are under `runs/D/eval-D-20261024-213556/`; the earlier D iterations remain alongside them. The final D pass cost **$0.008564** across logged calls (the rounded per-candidate summary reports $0.008565), including simulator calls. Total spend across all recorded experiment iterations is **$0.433376** of the $3.00 ceiling.

![Cost versus accuracy by variant](cost_vs_accuracy.png)

## Reproducibility and artifacts

Fixed IDs: `SYN001, SYN002, SYN003, SYN007, SYN008, SYN009, SYN010, SYN015, SYN016, SYN017, SYN020, SYN023`. Per-variant results, transcripts, usage, and safety logs are in `evidence/cost_experiment/runs/`.

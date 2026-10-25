# Partial evaluation — eval-20261024-192156

This was an intentionally stopped iteration, not a complete 24-persona evaluation. One candidate (SYN001) completed the screening questions, but verification failed because the 800-character candidate-message guard was incorrectly applied to the verifier's full transcript payload. The remaining 23 personas were not run. The observed safety event and model-call log are preserved here as evidence of the defect.

The defect is fixed in eligibl/llm.py: the candidate-message length guard now applies only to candidate_screener, not screening_verifier. A regression test uses a verifier payload longer than 800 characters. The next run is the full validation run.

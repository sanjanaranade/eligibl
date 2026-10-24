"""Deterministic candidate classification; the AI verifier cannot choose it."""

from __future__ import annotations


def classify_candidate(
    answers: list[dict],
    *,
    concerns: list[dict] | bool = False,
    injection_flag: bool = False,
    required_criteria: list[str] | None = None,
    verification_complete: bool = True,
) -> str:
    """Apply the project decision precedence to criterion verdicts."""
    if concerns or injection_flag:
        return "Flagged"
    verdicts = {row["criterion_id"]: row["verdict"] for row in answers}
    if any(value in {"not_satisfied", "not_met"} for value in verdicts.values()):
        return "Not a match"
    if not verification_complete:
        return "Needs review"
    if any(value in {"unclear", "unknown"} for value in verdicts.values()):
        return "Needs review"
    required = set(required_criteria or verdicts)
    if required and all(verdicts.get(criterion) in {"satisfied", "met"} for criterion in required):
        return "Likely eligible"
    return "Needs review"

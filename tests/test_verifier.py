"""Verifier provenance checks and the AI's downgrade-only boundary."""

import json

from eligibl.agents import verifier
from eligibl.config import REPO_ROOT
from eligibl.db import (
    coordinator_candidates,
    create_candidate_screening,
    flag_injection,
    get_criterion_answers,
    get_safety_events,
    init_db,
    save_candidate_message,
    save_criterion_answer,
    save_verification,
)


def _candidate(tmp_path):
    protocol = json.loads((REPO_ROOT / "data" / "protocol.json").read_text(encoding="utf-8"))
    database = str(tmp_path / "verify.db")
    init_db(database)
    create_candidate_screening(database, "verify-candidate", "Maya", protocol)
    return protocol, database


def test_quote_match_is_case_and_whitespace_insensitive_and_allows_90_percent_fuzzy():
    assert verifier.quote_in_transcript("I AM   29", ["I am 29 years old"])
    assert verifier.quote_in_transcript("I am 29 year old", ["I am 29 years old"])
    assert verifier.quote_in_transcript("I am 29 years old", ["I am 29 years old today"])
    assert not verifier.quote_in_transcript("I am 29", ["I am 39 years old"])
    assert not verifier.quote_in_transcript("I am 29", [])


def test_missing_candidate_quote_is_downgraded_and_safety_logged(tmp_path, monkeypatch):
    _protocol, database = _candidate(tmp_path)
    save_candidate_message(database, "verify-candidate", "assistant", "I am 29 years old")
    save_criterion_answer(database, "verify-candidate", "C1", "satisfied", "I am 29", "age")
    monkeypatch.setattr(verifier, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        verifier, "call_agent",
        lambda *args, **kwargs: (json.dumps({"summary": "No candidate text was supplied.", "downgrades": []}), {}),
    )

    result = verifier.verify_screening(database, "verify-candidate")

    answer = get_criterion_answers(database, "verify-candidate")[0]
    assert result["status"] == "complete"
    assert answer["verdict"] == "unknown"
    assert answer["note"] == "Evidence not found in transcript"
    assert get_safety_events(database)[0]["event"] == "verifier_quote_missing"


def test_model_can_only_downgrade_satisfied_answers(tmp_path, monkeypatch):
    _protocol, database = _candidate(tmp_path)
    save_candidate_message(database, "verify-candidate", "user", "I am 29 years old.")
    save_candidate_message(database, "verify-candidate", "user", "I am willing to attend visits.")
    save_criterion_answer(database, "verify-candidate", "C1", "satisfied", "I am 29 years old", "Age stated")
    save_criterion_answer(database, "verify-candidate", "C5", "not_satisfied", "I am willing to attend visits", "Negative")

    def fake_call(*_args, **_kwargs):
        return json.dumps({
            "summary": "The candidate reports their age and willingness; one answer is negative.",
            "downgrades": [
                {"criterion_id": "C1", "reason": "Age evidence is ambiguous."},
                {"criterion_id": "C5", "reason": "Attempt to alter a negative verdict."},
                {"criterion_id": "C999", "reason": "Unknown criterion."},
            ],
        }), {}

    monkeypatch.setattr(verifier, "call_agent", fake_call)
    result = verifier.verify_screening(database, "verify-candidate")
    answers = {row["criterion_id"]: row for row in get_criterion_answers(database, "verify-candidate")}

    assert result["downgrades"] == [{"criterion_id": "C1", "reason": "Age evidence is ambiguous."}]
    assert answers["C1"]["verdict"] == "unknown"
    assert answers["C5"]["verdict"] == "not_met"


def test_optional_verifier_skip_still_checks_evidence_and_only_skips_not_matches(tmp_path, monkeypatch):
    protocol, database = _candidate(tmp_path)
    save_candidate_message(database, "verify-candidate", "user", "I am 17 years old.")
    save_criterion_answer(database, "verify-candidate", "C1", "not_satisfied", "I am 17 years old", "Below minimum age.")
    monkeypatch.setattr(
        verifier, "call_agent",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("AI verifier should have been skipped")),
    )

    result = verifier.verify_screening(database, "verify-candidate", skip_ai_when_not_match=True)

    assert result["status"] == "skipped"
    assert "coordinator must still review" in result["summary"]
    assert coordinator_candidates(database)[0]["decision_label"] == "Not a match"


def test_optional_verifier_skip_does_not_skip_flagged_or_unclear_cases(tmp_path, monkeypatch):
    _protocol, database = _candidate(tmp_path)
    save_candidate_message(database, "verify-candidate", "user", "I am 29 years old.")
    save_criterion_answer(database, "verify-candidate", "C1", "satisfied", "I am 29 years old", "Age stated.")
    called = []
    monkeypatch.setattr(
        verifier, "call_agent",
        lambda *_args, **_kwargs: called.append(True) or ({"summary": "Reviewed.", "downgrades": []}, {}),
    )

    result = verifier.verify_screening(database, "verify-candidate", skip_ai_when_not_match=True)

    assert result["status"] == "complete"
    assert called == [True]


def test_injection_flag_is_a_safety_event_and_coordinator_concern(tmp_path):
    from eligibl.db import get_candidate_concerns, has_injection_flag

    _protocol, database = _candidate(tmp_path)
    log_path = tmp_path / "safety.jsonl"
    flag_injection(database, "verify-candidate", "Instruction-like request detected.", log_path)

    assert has_injection_flag(database, "verify-candidate")
    assert "Possible prompt injection" in get_candidate_concerns(database, "verify-candidate")[0]["reason"]
    assert json.loads(log_path.read_text(encoding="utf-8"))["event"] == "candidate_injection_flag"
    assert coordinator_candidates(database)[0]["display_status"] == "Flagged"
    save_verification(database, "verify-candidate", "Review needed.", "complete")
    assert coordinator_candidates(database)[0]["decision_label"] == "Flagged"

"""Decision precedence must stay deterministic and independent of model output."""

import pytest

from eligibl.decision import classify_candidate


@pytest.mark.parametrize(
    ("answers", "concerns", "injection", "required", "verified", "expected"),
    [
        ([{"criterion_id": "C1", "verdict": "not_met"}], [{"reason": "flag"}], False, ["C1"], True, "Flagged"),
        ([{"criterion_id": "C1", "verdict": "not_met"}], [], True, ["C1"], True, "Flagged"),
        ([{"criterion_id": "C1", "verdict": "not_met"}, {"criterion_id": "C2", "verdict": "unknown"}], [], False, ["C1", "C2"], True, "Not a match"),
        ([{"criterion_id": "C1", "verdict": "unknown"}], [], False, ["C1"], True, "Needs review"),
        ([{"criterion_id": "C1", "verdict": "met"}], [], False, ["C1", "C2"], True, "Needs review"),
        ([{"criterion_id": "C1", "verdict": "met"}], [], False, ["C1"], False, "Needs review"),
        ([{"criterion_id": "C1", "verdict": "met"}, {"criterion_id": "C2", "verdict": "satisfied"}], [], False, ["C1", "C2"], True, "Likely eligible"),
    ],
)
def test_decision_precedence(answers, concerns, injection, required, verified, expected):
    assert classify_candidate(
        answers, concerns=concerns, injection_flag=injection,
        required_criteria=required, verification_complete=verified,
    ) == expected

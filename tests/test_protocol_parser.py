"""Offline tests for protocol extraction, validation, and hash caching."""

import json

import pytest

from eligibl.agents import protocol_parser as parser
from eligibl.agents.screening_tools import BMI_TOOL, calculate_bmi


SOURCE = """Study title: Sample Sleep Study
NCT number: NCT01234567

Eligibility Criteria:

Inclusion Criteria:
* Age 18 years or older
* Lab value within range

Exclusion Criteria:
* Does not have untreated sleep apnea
"""


def parsed_result(source=SOURCE):
    """Make a deterministic schema-shaped result matching the test source."""
    _title, _nct, criteria = parser._source_metadata(source)
    return {
        "study_title": "Sample Sleep Study",
        "nct_id": "NCT01234567",
        "candidate_summary": "Researchers are studying sleep in adults. The study includes visits and questions.",
        "criteria": [
            {
                "id": f"C{index}",
                "type": kind,
                "original_text": text,
                "requirement": "Does NOT have the condition." if kind == "exclusion" else "Is age 18 years or older.",
                "screening_question": "Is this true for you?",
                "satisfied_when": "The person clearly confirms this.",
                "unclear_when": "The answer is uncertain or needs records.",
                "requires_clinic_check": text.startswith("Lab"),
            }
            for index, (kind, text) in enumerate(criteria, start=1)
        ],
    }


def test_validate_protocol_binds_identity_order_and_original_text():
    result = parser.validate_protocol(parsed_result(), SOURCE)

    assert result["nct_id"] == "NCT01234567"
    assert [row["id"] for row in result["criteria"]] == ["C1", "C2", "C3"]
    assert result["criteria"][1]["requires_clinic_check"] is True


def test_exclusion_requirement_must_be_phrased_as_absence():
    result = parsed_result()
    result["criteria"][2]["requirement"] = "Has a history of this condition."

    with pytest.raises(parser.ProtocolValidationError, match="phrased as absence"):
        parser.validate_protocol(result, SOURCE)


def test_validator_rejects_missing_source_criteria():
    result = parsed_result()
    result["criteria"].pop()

    with pytest.raises(parser.ProtocolValidationError, match="count does not match"):
        parser.validate_protocol(result, SOURCE)


def test_bmi_criterion_asks_for_height_and_weight_and_can_be_chat_screened():
    bmi_source = SOURCE.replace("* Lab value within range", "* BMI between 18 and 35 kg/m²")
    result = parsed_result(bmi_source)

    protocol = parser.validate_protocol(result, bmi_source)
    bmi = protocol["criteria"][1]

    assert "height and weight" in bmi["screening_question"]
    assert "Calculate BMI" in bmi["satisfied_when"]
    assert bmi["requires_clinic_check"] is False


@pytest.mark.parametrize(
    ("weight", "height", "weight_unit", "height_unit", "expected"),
    [
        (68, 170, "kg", "cm", 23.5),
        (150, 67, "lb", "in", 23.5),
        (68, 1.7, "kg", "m", 23.5),
    ],
)
def test_calculate_bmi_supports_metric_and_imperial(weight, height, weight_unit, height_unit, expected):
    assert calculate_bmi(weight, height, weight_unit=weight_unit, height_unit=height_unit) == expected


def test_calculate_bmi_rejects_unknown_units_and_nonpositive_values():
    with pytest.raises(ValueError, match="weight_unit"):
        calculate_bmi(68, 170, weight_unit="stone")
    with pytest.raises(ValueError, match="greater than zero"):
        calculate_bmi(0, 170)


def test_bmi_tool_is_registered_with_call_agent_compatible_schema():
    assert BMI_TOOL["schema"]["name"] == "calculate_bmi"
    assert BMI_TOOL["handler"](weight=68, weight_unit="kg", height=170, height_unit="cm") == 23.5


def test_parser_cache_skips_model_until_source_changes(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    source_path = data_dir / "protocol_source.txt"
    source_path.write_text(SOURCE, encoding="utf-8")
    monkeypatch.setattr(parser, "SOURCE_PATH", source_path)
    monkeypatch.setattr(parser, "OUTPUT_PATH", tmp_path / "protocol.json")
    monkeypatch.setattr(parser, "HASH_PATH", tmp_path / "protocol.sha256")
    calls = []

    def fake_call_agent(*args, **kwargs):
        calls.append((args, kwargs))
        return parsed_result(), {"input": 10, "output": 20}

    monkeypatch.setattr(parser, "call_agent", fake_call_agent)
    first = parser.parse_protocol(source_path)
    second = parser.parse_protocol(source_path)

    assert first == second
    assert len(calls) == 1
    assert json.loads((tmp_path / "protocol.json").read_text()) == first
    assert (tmp_path / "protocol.sha256").exists()

    source_path.write_text(SOURCE.replace("Age 18 years or older", "Age 21 years or older"), encoding="utf-8")
    with pytest.raises(parser.ProtocolValidationError, match="does not preserve"):
        parser.parse_protocol(source_path)
    assert len(calls) == 2

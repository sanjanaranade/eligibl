"""Deterministic calculations suitable for trusted screening-agent tools."""

from __future__ import annotations

import re
from typing import Any


_WEIGHT_PATTERN = re.compile(
    r"\b(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>kgs?|kilograms?|lbs?|pounds?)\b", re.I
)
_METRIC_HEIGHT_PATTERN = re.compile(
    r"\b(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>cm|centimeters?|m|meters?)\b", re.I
)
_IMPERIAL_HEIGHT_PATTERN = re.compile(
    r"\b(?P<feet>\d{1,2})\s*(?:ft|feet|foot|')\s*(?P<inches>\d{1,2}(?:\.\d+)?)?\s*(?:inch(?:es)?|in|\")?(?!\w)", re.I
)


def _weight_kg(text: str) -> tuple[float | None, bool]:
    """Return one unambiguous reported weight normalized to kg."""
    values = []
    for match in _WEIGHT_PATTERN.finditer(text):
        value = float(match.group("value"))
        unit = match.group("unit").casefold()
        values.append(value * 0.45359237 if unit.startswith(("lb", "pound")) else value)
    if not values:
        return None, False
    if max(values) - min(values) > 0.5:
        return None, True
    value = values[-1]
    return (value, False) if 20 <= value <= 500 else (None, True)


def _height_cm(text: str) -> tuple[float | None, bool]:
    """Return one unambiguous reported height normalized to cm."""
    values = []
    for match in _METRIC_HEIGHT_PATTERN.finditer(text):
        value = float(match.group("value"))
        unit = match.group("unit").casefold()
        values.append(value * 100 if unit in {"m", "meter", "meters"} else value)
    for match in _IMPERIAL_HEIGHT_PATTERN.finditer(text):
        feet = int(match.group("feet"))
        inches = float(match.group("inches") or 0)
        values.append((feet * 12 + inches) * 2.54)
    if not values:
        return None, False
    if max(values) - min(values) > 2:
        return None, True
    value = values[-1]
    return (value, False) if 100 <= value <= 250 else (None, True)


def extract_bmi_measurements(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Accumulate explicit participant measurements across turns, never assistant text.

    A later user message can clarify or update an earlier value. Conflicting
    measurements in a single message are surfaced as ambiguous instead of guessed.
    """
    height_cm: float | None = None
    weight_kg: float | None = None
    height_ambiguous = False
    weight_ambiguous = False
    latest_has_measurement = False
    for index, message in enumerate(messages):
        if message.get("role") != "user":
            continue
        text = str(message.get("content", ""))
        reported_weight, weight_conflict = _weight_kg(text)
        reported_height, height_conflict = _height_cm(text)
        has_measurement = reported_weight is not None or reported_height is not None or weight_conflict or height_conflict
        if reported_weight is not None or weight_conflict:
            weight_kg, weight_ambiguous = reported_weight, weight_conflict
        if reported_height is not None or height_conflict:
            height_cm, height_ambiguous = reported_height, height_conflict
        if has_measurement:
            latest_has_measurement = index == len(messages) - 1
    return {
        "height_cm": round(height_cm, 2) if height_cm is not None else None,
        "weight_kg": round(weight_kg, 2) if weight_kg is not None else None,
        "height_ambiguous": height_ambiguous,
        "weight_ambiguous": weight_ambiguous,
        "latest_has_measurement": latest_has_measurement,
    }


def calculate_bmi(
    weight: float,
    height: float,
    *,
    weight_unit: str = "kg",
    height_unit: str = "cm",
) -> float:
    """Calculate BMI from positive measurements; return kg/m² rounded to one decimal.

    Supported weight units are kg and lb/lbs. Supported height units are m, cm,
    ft (decimal feet), and in/inches. Natural-language values must be converted
    to a numeric value and unit by trusted application code before calling.
    """
    try:
        weight_value = float(weight)
        height_value = float(height)
    except (TypeError, ValueError) as exc:
        raise ValueError("Height and weight must be numeric values.") from exc
    if weight_value <= 0 or height_value <= 0:
        raise ValueError("Height and weight must be greater than zero.")

    weight_key = weight_unit.strip().casefold()
    height_key = height_unit.strip().casefold()
    if weight_key in {"lb", "lbs"}:
        weight_kg = weight_value * 0.45359237
    elif weight_key == "kg":
        weight_kg = weight_value
    else:
        raise ValueError("weight_unit must be kg, lb, or lbs.")

    if height_key == "cm":
        height_m = height_value / 100
    elif height_key == "m":
        height_m = height_value
    elif height_key in {"in", "inch", "inches"}:
        height_m = height_value * 0.0254
    elif height_key == "ft":
        height_m = height_value * 0.3048
    else:
        raise ValueError("height_unit must be cm, m, ft, or in/inches.")

    if height_m <= 0:
        raise ValueError("Height must be greater than zero.")
    return round(weight_kg / (height_m * height_m), 1)


BMI_TOOL = {
    "schema": {
        "type": "function",
        "name": "calculate_bmi",
        "description": "Calculate BMI from candidate-provided height and weight; this does not decide eligibility.",
        "parameters": {
            "type": "object",
            "properties": {
                "weight": {"type": "number", "description": "Candidate-reported weight."},
                "weight_unit": {"type": "string", "enum": ["kg", "lb", "lbs"]},
                "height": {"type": "number", "description": "Height in the specified unit; convert feet-and-inches to total inches first."},
                "height_unit": {"type": "string", "enum": ["cm", "m", "ft", "in"]},
            },
            "required": ["weight", "weight_unit", "height", "height_unit"],
            "additionalProperties": False,
        },
    },
    "handler": calculate_bmi,
}

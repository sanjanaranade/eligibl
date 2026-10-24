"""Deterministic calculations suitable for trusted screening-agent tools."""

from __future__ import annotations


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

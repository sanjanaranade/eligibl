"""Agent 5: create a concise PI update from aggregate screening statistics only."""

from __future__ import annotations

from typing import Any

from ..analytics import weekly_funnel_stats
from ..llm import call_agent, compose_messages


AGENT_NAME = "weekly_insights"
SUMMARY_SCHEMA = {
    "name": "weekly_pi_summary",
    "schema": {
        "type": "object",
        "properties": {"summary": {"type": "string"}},
        "required": ["summary"],
        "additionalProperties": False,
    },
}


def _sentence_count(text: str) -> int:
    """Count simple prose sentences for enforcing the 3–4 sentence brief."""
    import re

    return len([part for part in re.split(r"(?<=[.!?])\s+", text.strip()) if part])


def summarize_week(database: str, timezone_name: str = "UTC") -> dict[str, Any]:
    """Call the model with one aggregate-only tool and return a validated summary."""
    tool = {
        "schema": {
            "type": "function",
            "name": "get_funnel_stats",
            "description": "Fetch weekly aggregate funnel, criterion-failure, and screening metrics. Contains no candidate-level data.",
            "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
        },
        "handler": lambda: weekly_funnel_stats(database, timezone_name),
    }
    prompt = (
        "Write exactly 3 or 4 concise sentences for a study principal investigator. "
        "First call get_funnel_stats. Summarize the funnel, notable common criterion failures, "
        "and screening workload. Make practical suggestions only when supported by these counts; "
        "state when the sample is small or empty. Do not infer causes or make clinical claims."
    )
    result, usage = call_agent(
        AGENT_NAME,
        compose_messages(
            "You are a careful clinical-research operations analyst. You receive aggregate statistics only; never request individual records.",
            "Use only the single registered aggregate tool. Do not invent explanations for observed counts.",
            [{"role": "user", "content": prompt}],
        ),
        tools={"get_funnel_stats": tool},
        response_schema=SUMMARY_SCHEMA,
        max_output_tokens=500,
    )
    if not usage.get("tool_calls"):
        raise RuntimeError("Insights did not retrieve the required aggregate metrics.")
    summary = " ".join(str(result.get("summary", "")).split())
    if _sentence_count(summary) not in {3, 4}:
        raise RuntimeError("Insights returned an invalid summary length; please try again.")
    return {"summary": summary, "usage": usage}


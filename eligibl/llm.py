"""Centralized, auditable OpenAI-compatible client for Portkey model calls."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from openai import OpenAI

from .config import MODEL_NAME, PORTKEY_BASE_URL
from .db import log_model_call


# Course-project reference rates, USD per million tokens. Cached input is
# counted separately in logs; this conservative estimate prices it at input rate.
INPUT_USD_PER_MILLION = 0.15
OUTPUT_USD_PER_MILLION = 0.60
DEFAULT_DATABASE = Path(__file__).resolve().parents[1] / "data" / "eligibl.sqlite3"


def create_client() -> OpenAI:
    """Create the Portkey client using the established coursework setup."""
    api_key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is missing; add it to the project or parent .env file.")
    return OpenAI(
        api_key=api_key,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-provider": "openai"},
    )


def _usage_value(usage: Any, name: str, default: int = 0) -> int:
    """Read a usage field from an SDK object or a dictionary-shaped test double."""
    if isinstance(usage, dict):
        value = usage.get(name, default)
    else:
        value = getattr(usage, name, default)
    return int(value or 0)


def _cached_tokens(usage: Any) -> int:
    """Extract cached input token count across Responses API SDK shapes."""
    details = usage.get("input_tokens_details", {}) if isinstance(usage, dict) else getattr(
        usage, "input_tokens_details", None
    )
    if details is None:
        return 0
    return _usage_value(details, "cached_tokens")


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost using the course reference rates per million tokens."""
    return (
        input_tokens * INPUT_USD_PER_MILLION
        + output_tokens * OUTPUT_USD_PER_MILLION
    ) / 1_000_000


def request_text(
    *,
    agent: str,
    candidate_id: str | None,
    instructions: str,
    input_text: str,
    database: str | Path = DEFAULT_DATABASE,
    client: Any | None = None,
) -> str:
    """Call gpt-6-luna and log usage, latency, and outcome without prompt text."""
    active_client = client or create_client()
    started = time.perf_counter()
    usage = None
    outcome = "error"
    error_type = None
    try:
        response = active_client.responses.create(
            model=MODEL_NAME,
            instructions=instructions,
            input=input_text,
        )
        usage = getattr(response, "usage", None)
        outcome = "success"
        return str(getattr(response, "output_text", ""))
    except Exception as exc:
        error_type = type(exc).__name__
        raise
    finally:
        latency_ms = (time.perf_counter() - started) * 1000
        input_tokens = _usage_value(usage, "input_tokens") if usage is not None else None
        output_tokens = _usage_value(usage, "output_tokens") if usage is not None else None
        cached_input_tokens = _cached_tokens(usage) if usage is not None else None
        cost = (
            estimate_cost_usd(input_tokens, output_tokens)
            if input_tokens is not None and output_tokens is not None
            else None
        )
        log_model_call(
            database,
            {
                "agent": agent,
                "candidate_id": candidate_id,
                "model": MODEL_NAME,
                "input_tokens": input_tokens,
                "cached_input_tokens": cached_input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": cost,
                "latency_ms": latency_ms,
                "outcome": outcome,
                "error_type": error_type,
            },
        )

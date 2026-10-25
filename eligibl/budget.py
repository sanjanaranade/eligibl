"""Pricing and call-limit helpers for model requests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
PRICING_PATH = REPO_ROOT / "config" / "pricing.json"
LIMITS_PATH = REPO_ROOT / "config" / "limits.json"


class BudgetExceeded(RuntimeError):
    """Raised when a configured screening, token, tool, or dollar limit is hit."""

    def __init__(self, limit_name: str, message: str):
        super().__init__(message)
        self.limit_name = limit_name


def _load_json(path: str | Path) -> dict[str, Any]:
    """Read a JSON configuration file."""
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def load_pricing(path: str | Path = PRICING_PATH) -> dict[str, Any]:
    """Load per-token pricing configuration."""
    return _load_json(path)


def load_limits(path: str | Path | None = None) -> dict[str, Any]:
    """Load runtime guardrail limits."""
    return _load_json(path or LIMITS_PATH)


def compute_cost_usd(
    input_tokens: int,
    cached_input_tokens: int,
    output_tokens: int,
    pricing: dict[str, Any] | None = None,
) -> float:
    """Compute cost from token counts and USD-per-million rates."""
    rates = (pricing or load_pricing()).get("rates_usd_per_1m_tokens", {})
    input_rate = rates.get("input")
    cached_rate = rates.get("cached_input")
    output_rate = rates.get("output")
    if any(rate is None for rate in (input_rate, cached_rate, output_rate)):
        raise ValueError("All input, cached-input, and output prices must be configured.")
    if min(input_tokens, cached_input_tokens, output_tokens) < 0:
        raise ValueError("Token counts cannot be negative.")
    if cached_input_tokens > input_tokens:
        raise ValueError("Cached input tokens cannot exceed total input tokens.")

    uncached_tokens = input_tokens - cached_input_tokens
    total = (
        uncached_tokens * float(input_rate)
        + cached_input_tokens * float(cached_rate)
        + output_tokens * float(output_rate)
    )
    return total / 1_000_000


def estimate_input_tokens(messages: Any) -> int:
    """Conservatively approximate prompt tokens as half the serialized UTF-8 bytes.

    This errs high for ordinary English prompts without treating every byte as
    a token, which otherwise blocks multi-turn chats well before the configured
    token cap. Provider-reported usage remains the source of recorded totals.
    """
    def encode_object(value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "__dict__"):
            return vars(value)
        return str(value)

    serialized = json.dumps(
        messages,
        ensure_ascii=False,
        separators=(",", ":"),
        default=encode_object,
    )
    byte_count = len(serialized.encode("utf-8"))
    return (byte_count + 1) // 2

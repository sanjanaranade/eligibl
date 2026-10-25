"""Centralized Portkey model calls, tool loops, usage accounting, and guardrails."""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from openai import APIError, OpenAI

from .budget import (
    LIMITS_PATH,
    PRICING_PATH,
    BudgetExceeded,
    compute_cost_usd,
    estimate_input_tokens,
    load_limits,
    load_pricing,
)
from .config import MODEL_NAME, PORTKEY_BASE_URL, REPO_ROOT
from .db import (
    candidate_totals,
    log_model_call,
    record_safety_event,
    record_trace_step,
    reserve_screening_turn,
    usage_totals_today,
)


DEFAULT_DATABASE = REPO_ROOT / "data" / "eligibl.sqlite3"
USAGE_LOG_PATH = REPO_ROOT / "logs" / "usage.jsonl"
SAFETY_LOG_PATH = REPO_ROOT / "logs" / "safety.jsonl"
COST_EXPERIMENT_SPEND_GUARD: Any = None
_SECRET_PATTERN = re.compile(r"(?i)(portkey_api_key|api[_ -]?key|access[_ -]?token|secret|bearer)\s*[:=]\s*[^\s,;]+")


def create_client() -> OpenAI:
    """Create the OpenAI-compatible client using the proven course setup."""
    api_key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is missing; add it to the project or parent .env file.")
    return OpenAI(
        api_key=api_key,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-provider": "openai"},
    )


def compose_messages(
    system_prompt: str,
    protocol_checklist: str,
    variable_messages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build a byte-stable system/checklist prefix followed by variable messages."""
    static_prefix = f"{system_prompt.rstrip()}\n\nProtocol checklist:\n{protocol_checklist.rstrip()}"
    return [{"role": "system", "content": static_prefix}, *variable_messages]


def _value(obj: Any, key: str, default: Any = None) -> Any:
    """Read an API field from either an SDK object or a dict-shaped test double."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _usage(response: Any) -> dict[str, int]:
    """Normalize Responses API token usage; absent cached-token details mean zero."""
    usage = _value(response, "usage")
    if usage is None:
        return {"input": 0, "cached_input": 0, "output": 0}
    raw_input_tokens = _value(usage, "input_tokens")
    if raw_input_tokens is None:
        raw_input_tokens = _value(usage, "prompt_tokens", 0)
    input_tokens = int(raw_input_tokens or 0)
    output_tokens = int(_value(usage, "output_tokens", 0) or 0)
    details = _value(usage, "input_tokens_details")
    if details is None:
        details = _value(usage, "prompt_tokens_details")
    cached = int(_value(details, "cached_tokens", 0) or 0) if details is not None else 0
    return {"input": input_tokens, "cached_input": cached, "output": output_tokens}


def _response_schema_format(response_schema: Any) -> dict[str, Any] | None:
    """Convert a JSON Schema or Pydantic model into Responses API JSON output mode."""
    if response_schema is None:
        return None
    if hasattr(response_schema, "model_json_schema"):
        schema = response_schema.model_json_schema()
        name = getattr(response_schema, "__name__", "structured_response")
    elif isinstance(response_schema, dict) and "schema" in response_schema:
        schema = response_schema["schema"]
        name = response_schema.get("name", schema.get("title", "structured_response"))
    elif isinstance(response_schema, dict):
        schema = response_schema
        name = schema.get("title", "structured_response")
    else:
        raise TypeError("response_schema must be a JSON Schema or Pydantic model class.")
    return {
        "format": {
            "type": "json_schema",
            "name": re.sub(r"[^A-Za-z0-9_-]", "_", str(name))[:64],
            "schema": schema,
            "strict": True,
        }
    }


def _tool_registry(tools: Any) -> tuple[list[dict[str, Any]], dict[str, Callable[..., Any]]]:
    """Normalize app-owned tool schemas and callable handlers for Responses API."""
    if not tools:
        return [], {}
    if not isinstance(tools, Mapping):
        raise TypeError("tools must be a mapping of trusted tool names to schema/handler entries.")
    api_tools: list[dict[str, Any]] = []
    handlers: dict[str, Callable[..., Any]] = {}
    for tool_name, definition in tools.items():
        if not isinstance(definition, Mapping):
            raise TypeError(f"Tool {tool_name!r} must define a schema and handler.")
        schema = definition.get("schema", definition.get("definition"))
        handler = definition.get("handler")
        if not isinstance(schema, Mapping) or not callable(handler):
            raise TypeError(f"Tool {tool_name!r} needs a schema and trusted callable handler.")
        function = schema.get("function", schema)
        name = str(function.get("name", tool_name))
        api_tools.append({
            "type": "function",
            "name": name,
            "description": str(function.get("description", "")),
            "parameters": function.get("parameters", {"type": "object", "properties": {}}),
            "strict": bool(function.get("strict", False)),
        })
        handlers[name] = handler
    return api_tools, handlers


def _tool_calls(response: Any) -> list[Any]:
    """Extract function-call items from a Responses API result."""
    return [item for item in (_value(response, "output", []) or []) if _value(item, "type") == "function_call"]


def _messages_payload(messages: Any) -> list[dict[str, Any]]:
    """Normalize messages and require stable instructions to precede user text."""
    if isinstance(messages, str):
        payload = [{"role": "user", "content": messages}]
    elif isinstance(messages, list) and messages:
        payload = [dict(message) for message in messages]
    else:
        raise ValueError("messages must be a non-empty string or list of message objects.")
    first_dynamic = next(
        (index for index, item in enumerate(payload) if item.get("role") not in ("system", "developer")),
        len(payload),
    )
    if first_dynamic == 0:
        raise ValueError("Start messages with the byte-stable system prompt and protocol checklist.")
    if any(item.get("role") in ("system", "developer") for item in payload[first_dynamic:]):
        raise ValueError("Static system/developer instructions must precede variable messages for prompt caching.")
    return payload


def _latest_user_text(messages: list[dict[str, Any]]) -> str:
    """Return the most recent user content as plain text for length checks/summaries."""
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content", "")
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                return " ".join(
                    str(part.get("text", "")) if isinstance(part, dict) else str(part)
                    for part in content
                )
            return str(content)
    return ""


def _candidate_text_for_limit(user_text: str) -> str:
    """Unwrap JSON-delimited candidate data so only their text counts toward 800 chars."""
    prefix = "CANDIDATE_MESSAGE_JSON:"
    if user_text.startswith(prefix):
        try:
            value = json.loads(user_text[len(prefix):])
            return value if isinstance(value, str) else user_text
        except json.JSONDecodeError:
            return user_text
    return user_text


def _screening_agent(agent_name: str) -> bool:
    """Identify candidate-facing screener agents whose turns are capped."""
    return agent_name.casefold() == "candidate_screener"


def _safe_summary(value: str, maximum: int = 220) -> str:
    """Create a short trace summary while masking common secret assignments."""
    clean = _SECRET_PATTERN.sub("[redacted]", value)
    clean = " ".join(clean.split())
    return clean[:maximum]


def _redact_tool_values(value: Any) -> Any:
    """Redact likely credentials from structured tool arguments before tracing."""
    if isinstance(value, Mapping):
        safe = {}
        for key, item in value.items():
            name = str(key).casefold()
            if any(part in name for part in ("api_key", "apikey", "secret", "password", "credential", "authorization", "token")):
                safe[str(key)] = "[redacted]"
            else:
                safe[str(key)] = _redact_tool_values(item)
        return safe
    if isinstance(value, list):
        return [_redact_tool_values(item) for item in value]
    if isinstance(value, str):
        return _SECRET_PATTERN.sub("[redacted]", value)
    return value


def _record_usage(
    *,
    database: Path,
    log_path: Path,
    agent_name: str,
    candidate_id: str | None,
    run_id: str,
    usage: dict[str, int],
    latency_ms: float,
    outcome: str,
    pricing: dict[str, Any],
    error_type: str | None = None,
) -> float:
    """Write one API attempt to SQLite and committed JSONL; return its cost."""
    cost = compute_cost_usd(usage["input"], usage["cached_input"], usage["output"], pricing)
    log_model_call(
        database,
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent_name,
            "candidate_id": candidate_id,
            "run_id": run_id,
            "model": MODEL_NAME,
            "input_tokens": usage["input"],
            "cached_input_tokens": usage["cached_input"],
            "output_tokens": usage["output"],
            "cost_usd": cost,
            "latency_ms": latency_ms,
            "outcome": outcome,
            "error_type": error_type,
        },
        log_path,
    )
    return cost


def _preflight(
    *,
    messages: list[Any],
    agent_name: str,
    candidate_id: str | None,
    run_id: str,
    database: Path,
    safety_log: Path,
    limits: dict[str, Any],
    pricing: dict[str, Any],
    output_limit: int | None = None,
) -> int:
    """Check dollar and cumulative candidate-token budgets before every API call."""
    estimated_input = estimate_input_tokens(messages)
    configured_output = int(limits["max_output_tokens_per_call"])
    max_output = min(configured_output, int(output_limit)) if output_limit is not None else configured_output

    def reject(name: str, detail: str, observed: Any = None, maximum: Any = None) -> None:
        record_safety_event(
            database, safety_log,
            event="budget_limit_blocked",
            limit_name=name,
            details={"detail": detail, "observed": observed, "maximum": maximum},
            agent=agent_name,
            candidate_id=candidate_id,
            run_id=run_id,
        )
        raise BudgetExceeded(name, detail)

    if candidate_id:
        total = candidate_totals(database, candidate_id)["tokens"]
        projected = total + estimated_input + max_output
        maximum = int(limits["max_tokens_per_candidate"])
        if projected > maximum:
            reject("max_tokens_per_candidate", "Projected call would exceed the candidate token cap.", projected, maximum)

    current = usage_totals_today(database, limits["timezone"])
    projected_cost = compute_cost_usd(estimated_input, 0, max_output, pricing)
    if COST_EXPERIMENT_SPEND_GUARD is not None:
        # Reserve extra estimated headroom so an estimation mismatch cannot
        # consume the experiment's entire cap on the final model request.
        reserved_cost = projected_cost * 1.5
        reserved_total = COST_EXPERIMENT_SPEND_GUARD.spent_usd + reserved_cost
        if reserved_total > COST_EXPERIMENT_SPEND_GUARD.limit_usd:
            reject(
                "cost_experiment_usd",
                "The cost experiment reached its guarded spend ceiling; no further model call was made.",
                reserved_total,
                COST_EXPERIMENT_SPEND_GUARD.limit_usd,
            )
    projected_daily = float(current["cost_usd"]) + projected_cost
    daily_limit = float(limits["daily_budget_usd"])
    if projected_daily > daily_limit:
        reject("daily_budget_usd", "Projected call would exceed today's model budget.", projected_daily, daily_limit)
    return max_output


def _api_call_with_retries(
    *,
    client: Any,
    request: dict[str, Any],
    agent_name: str,
    candidate_id: str | None,
    run_id: str,
    messages: list[Any],
    database: Path,
    usage_log: Path,
    safety_log: Path,
    limits: dict[str, Any],
    pricing: dict[str, Any],
    output_limit: int | None = None,
) -> tuple[Any, dict[str, int], float]:
    """Make one model turn with at most two retries; log each attempt."""
    retry_count = min(2, max(0, int(limits.get("max_api_retries", 2))))
    backoff = float(limits.get("retry_backoff_seconds", 0.25))
    last_error: Exception | None = None
    for attempt in range(retry_count + 1):
        max_output = _preflight(
            messages=messages,
            agent_name=agent_name,
            candidate_id=candidate_id,
            run_id=run_id,
            database=database,
            safety_log=safety_log,
            limits=limits,
            pricing=pricing,
            output_limit=output_limit,
        )
        call_args = dict(request)
        call_args["max_output_tokens"] = max_output
        started = time.perf_counter()
        try:
            response = client.responses.create(**call_args)
        except Exception as exc:
            latency_ms = (time.perf_counter() - started) * 1000
            _record_usage(
                database=database, log_path=usage_log, agent_name=agent_name,
                candidate_id=candidate_id, run_id=run_id,
                usage={"input": 0, "cached_input": 0, "output": 0},
                latency_ms=latency_ms, outcome="error", pricing=pricing,
                error_type=type(exc).__name__,
            )
            last_error = exc
            if not isinstance(exc, APIError) or attempt >= retry_count:
                break
            time.sleep(backoff * (2 ** attempt))
            continue

        latency_ms = (time.perf_counter() - started) * 1000
        token_usage = _usage(response)
        _record_usage(
            database=database, log_path=usage_log, agent_name=agent_name,
            candidate_id=candidate_id, run_id=run_id, usage=token_usage,
            latency_ms=latency_ms, outcome="success", pricing=pricing,
        )
        return response, token_usage, latency_ms, attempt + 1
    assert last_error is not None
    raise last_error


def call_agent(
    agent_name: str,
    messages: Any,
    candidate_id: str | None = None,
    run_id: str | None = None,
    tools: Any = None,
    response_schema: Any = None,
    max_output_tokens: int | None = None,
) -> tuple[Any, dict[str, Any]]:
    """Call gpt-6-luna with optional trusted tools/schema and enforce budgets.

    `tools` maps server-owned names to `{"schema": ..., "handler": callable}`.
    `max_output_tokens` may lower (never raise) the configured per-call output cap.
    The model may select only these registered handlers; candidate text cannot add tools.
    Returns `(text_or_structured_result, aggregate_usage)`.
    """
    active_run_id = run_id or str(uuid.uuid4())
    payload = _messages_payload(messages)
    user_text = _latest_user_text(payload)
    database = Path(DEFAULT_DATABASE)
    usage_log = Path(USAGE_LOG_PATH)
    safety_log = Path(SAFETY_LOG_PATH)
    limits = load_limits(LIMITS_PATH)
    pricing = load_pricing(PRICING_PATH)
    registered_tools, handlers = _tool_registry(tools)

    aggregate = {"input": 0, "cached_input": 0, "output": 0, "cost_usd": 0.0, "latency_ms": 0.0, "calls": 0, "attempts": 0}
    observed_tool_calls: list[dict[str, Any]] = []
    result_text = ""
    completed = False

    def budget_reject(name: str, detail: str, observed: Any, maximum: Any) -> None:
        record_safety_event(
            database, safety_log, event="budget_limit_blocked", limit_name=name,
            details={"detail": detail, "observed": observed, "maximum": maximum},
            agent=agent_name, candidate_id=candidate_id, run_id=active_run_id,
        )
        raise BudgetExceeded(name, detail)

    try:
        if candidate_id and _screening_agent(agent_name):
            max_chars = int(limits["max_candidate_message_characters"])
            candidate_text = _candidate_text_for_limit(user_text)
            if len(candidate_text) > max_chars:
                budget_reject("max_candidate_message_characters", "Candidate message exceeds the configured character cap.", len(candidate_text), max_chars)
            try:
                _preflight(
                    messages=payload, agent_name=agent_name, candidate_id=candidate_id,
                    run_id=active_run_id, database=database, safety_log=safety_log,
                    limits=limits, pricing=pricing, output_limit=max_output_tokens,
                )
            except BudgetExceeded:
                raise
            maximum_turns = int(limits["max_screening_turns_per_candidate"])
            reserved = reserve_screening_turn(database, candidate_id, maximum_turns)
            if reserved is None:
                budget_reject("max_screening_turns_per_candidate", "Candidate has reached the screening-turn limit.", maximum_turns, maximum_turns)

        client = create_client()
        request: dict[str, Any] = {"model": MODEL_NAME, "input": payload}
        if registered_tools:
            request["tools"] = registered_tools
        schema_format = _response_schema_format(response_schema)
        if schema_format:
            request["text"] = schema_format

        tool_loops = 0
        while True:
            response, current_usage, latency, attempts = _api_call_with_retries(
                client=client,
                request=request,
                agent_name=agent_name,
                candidate_id=candidate_id,
                run_id=active_run_id,
                messages=payload,
                database=database,
                usage_log=usage_log,
                safety_log=safety_log,
                limits=limits,
                pricing=pricing,
                output_limit=max_output_tokens,
            )
            for key, token_key in (("input", "input"), ("cached_input", "cached_input"), ("output", "output")):
                aggregate[key] += current_usage[token_key]
            actual_call_cost = compute_cost_usd(
                current_usage["input"], current_usage["cached_input"], current_usage["output"], pricing
            )
            aggregate["cost_usd"] += actual_call_cost
            if COST_EXPERIMENT_SPEND_GUARD is not None:
                COST_EXPERIMENT_SPEND_GUARD.spent_usd += actual_call_cost
            aggregate["latency_ms"] += latency
            aggregate["calls"] += 1
            aggregate["attempts"] += attempts

            calls = _tool_calls(response)
            if not calls:
                result_text = str(_value(response, "output_text", "") or "")
                break
            if tool_loops >= int(limits["max_tool_call_loops_per_agent_turn"]):
                budget_reject(
                    "max_tool_call_loops_per_agent_turn",
                    "Agent requested another tool loop after reaching the configured limit.",
                    tool_loops + 1,
                    limits["max_tool_call_loops_per_agent_turn"],
                )
            tool_loops += 1
            if isinstance(payload, list):
                # Responses carry output-only metadata (for example `status`)
                # that Azure-backed Portkey rejects if echoed as input items.
                payload.extend(
                    {
                        "type": "function_call",
                        "call_id": str(_value(tool_call, "call_id", "")),
                        "name": str(_value(tool_call, "name", "")),
                        "arguments": str(_value(tool_call, "arguments", "{}")),
                    }
                    for tool_call in calls
                )
            terminal_tool_result = False
            for tool_call in calls:
                tool_name = str(_value(tool_call, "name", ""))
                raw_arguments = _value(tool_call, "arguments", "{}")
                try:
                    arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else dict(raw_arguments)
                except (json.JSONDecodeError, TypeError, ValueError):
                    # Tool arguments are model output, not trusted instructions. A
                    # truncated/malformed call must never reach a handler; return a
                    # bounded error to the model so it can reformulate the call.
                    record_safety_event(
                        database, safety_log, event="invalid_tool_arguments",
                        limit_name="tool_arguments",
                        details={"tool": tool_name, "detail": "Malformed JSON; tool was not executed."},
                        agent=agent_name, candidate_id=candidate_id, run_id=active_run_id,
                    )
                    payload.append({
                        "type": "function_call_output",
                        "call_id": _value(tool_call, "call_id", ""),
                        "output": json.dumps({
                            "error": "Arguments were not valid JSON. Retry the same registered tool with complete valid JSON."
                        }),
                    })
                    continue
                handler = handlers.get(tool_name)
                if handler is None:
                    budget_reject("unregistered_tool", "Model requested a tool not registered by the application.", tool_name, sorted(handlers))
                observed_tool_calls.append({"name": tool_name, "args": arguments})
                try:
                    tool_result = handler(**arguments)
                except Exception as exc:
                    tool_result = {"error": "Tool execution failed", "type": type(exc).__name__}
                if isinstance(tool_result, dict) and tool_result.get("_agent_turn_complete") is True:
                    # Some trusted tools perform a deterministic terminal
                    # transition. Do not spend another model request asking it
                    # to narrate a result the application already knows.
                    result_text = str(tool_result.get("_assistant_message", ""))
                    terminal_tool_result = True
                    continue
                payload.append({
                    "type": "function_call_output",
                    "call_id": _value(tool_call, "call_id", ""),
                    "output": tool_result if isinstance(tool_result, str) else json.dumps(tool_result, ensure_ascii=False),
                })
            if terminal_tool_result:
                break
            request["input"] = payload

        if response_schema is not None:
            result: Any = json.loads(result_text)
        else:
            result = result_text
        completed = True
        return result, {
            **aggregate,
            "model": MODEL_NAME,
            "run_id": active_run_id,
            "tool_calls": len(observed_tool_calls),
        }
    finally:
        total_usage = {
            "input": aggregate["input"],
            "cached_input": aggregate["cached_input"],
            "output": aggregate["output"],
        }
        try:
            record_trace_step(
                database,
                {
                    "run_id": active_run_id,
                    "candidate_id": candidate_id,
                    "agent": agent_name,
                    "input_summary": _safe_summary(user_text or "No user message."),
                    "tool_calls": _redact_tool_values(observed_tool_calls),
                    "output_summary": _safe_summary(result_text if completed else "Agent step stopped before a final response."),
                    "input_tokens": total_usage["input"],
                    "cached_input_tokens": total_usage["cached_input"],
                    "output_tokens": total_usage["output"],
                },
            )
        except Exception:
            # Preserve the primary agent error/result if trace storage itself fails.
            if completed:
                raise

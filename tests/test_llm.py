"""Mocked tests for usage math, budget controls, schemas, retries, and tools."""

import json
from types import SimpleNamespace

import pytest
import httpx
from openai import APIError

from eligibl import llm
from eligibl.budget import BudgetExceeded, compute_cost_usd
from eligibl.db import init_db


def response(text="ok", input_tokens=100, cached_tokens=20, output_tokens=25, output=None):
    return SimpleNamespace(
        output_text=text,
        output=output or [],
        usage=SimpleNamespace(
            input_tokens=input_tokens,
            input_tokens_details=SimpleNamespace(cached_tokens=cached_tokens),
            output_tokens=output_tokens,
        ),
    )


class FakeResponses:
    def __init__(self, answers):
        self.answers = list(answers)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


class FakeClient:
    def __init__(self, answers):
        self.responses = FakeResponses(answers)


def configure_test_paths(tmp_path, monkeypatch, *, limits=None):
    database = tmp_path / "test.sqlite3"
    usage_log = tmp_path / "usage.jsonl"
    safety_log = tmp_path / "safety.jsonl"
    init_db(database)
    monkeypatch.setattr(llm, "DEFAULT_DATABASE", database)
    monkeypatch.setattr(llm, "USAGE_LOG_PATH", usage_log)
    monkeypatch.setattr(llm, "SAFETY_LOG_PATH", safety_log)
    if limits is not None:
        path = tmp_path / "limits.json"
        path.write_text(json.dumps(limits), encoding="utf-8")
        monkeypatch.setattr(llm, "LIMITS_PATH", path)
    return database, usage_log, safety_log


def read_limits():
    return llm.load_limits()


def test_cost_math_uses_distinct_cached_input_rate():
    pricing = {
        "rates_usd_per_1m_tokens": {
            "input": 1.0,
            "cached_input": 0.25,
            "output": 2.0,
        }
    }
    assert compute_cost_usd(100, 20, 10, pricing) == pytest.approx(0.000105)


def test_preflight_prompt_estimate_is_conservative_without_counting_every_byte_as_a_token():
    messages = [{"role": "user", "content": "A short English prompt."}]
    serialized = json.dumps(messages, ensure_ascii=False, separators=(",", ":"))
    assert llm.estimate_input_tokens(messages) == (len(serialized.encode("utf-8")) + 1) // 2


def test_call_agent_can_lower_but_not_raise_configured_output_cap(tmp_path, monkeypatch):
    configure_test_paths(tmp_path, monkeypatch)
    client = FakeClient([response()])
    monkeypatch.setattr(llm, "create_client", lambda: client)
    messages = [{"role": "system", "content": "Fixed."}, {"role": "user", "content": "Reply."}]

    llm.call_agent("small_reply_agent", messages, max_output_tokens=70)

    assert client.responses.requests[0]["max_output_tokens"] == 70


def test_usage_is_logged_to_jsonl_database_and_trace(tmp_path, monkeypatch):
    database, usage_log, _ = configure_test_paths(tmp_path, monkeypatch)
    client = FakeClient([response()])
    monkeypatch.setattr(llm, "create_client", lambda: client)
    messages = llm.compose_messages(
        "Stable screener instructions.",
        "Check only the listed study criteria.",
        [{"role": "user", "content": "Reply with ok"}],
    )

    result, usage = llm.call_agent("demo_agent", messages, run_id="run-test-1")

    assert result == "ok"
    assert usage["model"] == "gpt-6-luna"
    assert usage["input"] == 100
    assert usage["cached_input"] == 20
    assert usage["output"] == 25
    assert len(client.responses.requests) == 1
    row = json.loads(usage_log.read_text(encoding="utf-8").splitlines()[0])
    assert row["agent"] == "demo_agent"
    assert row["run_id"] == "run-test-1"
    assert (row["input"], row["cached_input"], row["output"]) == (100, 20, 25)
    assert "Reply with ok" not in usage_log.read_text(encoding="utf-8")

    import sqlite3

    with sqlite3.connect(database) as connection:
        call = connection.execute(
            "SELECT agent, run_id, input_tokens, cached_input_tokens, output_tokens "
            "FROM model_call_logs"
        ).fetchone()
        trace = connection.execute(
            "SELECT run_id, step_number, agent, input_summary, output_summary, "
            "input_tokens, cached_input_tokens, output_tokens FROM agent_trace_steps"
        ).fetchone()
    assert call == ("demo_agent", "run-test-1", 100, 20, 25)
    assert trace[:3] == ("run-test-1", 1, "demo_agent")
    assert trace[3] == "Reply with ok"
    assert trace[4] == "ok"
    assert trace[5:] == (100, 20, 25)


def test_cached_prompt_prefix_is_byte_identical_before_variable_text():
    first = llm.compose_messages("Stable rules.", "Fixed checklist.", [{"role": "user", "content": "First"}])
    second = llm.compose_messages("Stable rules.", "Fixed checklist.", [{"role": "user", "content": "Different"}])
    assert first[0]["content"].encode() == second[0]["content"].encode()
    assert first[0]["content"] == "Stable rules.\n\nProtocol checklist:\nFixed checklist."
    assert first[1]["content"] != second[1]["content"]


def test_structured_output_schema_is_passed_and_decoded(tmp_path, monkeypatch):
    configure_test_paths(tmp_path, monkeypatch)
    client = FakeClient([response(text='{"verdict":"unknown"}')])
    monkeypatch.setattr(llm, "create_client", lambda: client)
    schema = {
        "title": "CriterionResult",
        "type": "object",
        "properties": {"verdict": {"type": "string"}},
        "required": ["verdict"],
        "additionalProperties": False,
    }

    result, _ = llm.call_agent(
        "eligibility_agent",
        [{"role": "system", "content": "Fixed."}, {"role": "user", "content": "Check."}],
        response_schema=schema,
    )

    assert result == {"verdict": "unknown"}
    assert client.responses.requests[0]["text"]["format"]["type"] == "json_schema"
    assert client.responses.requests[0]["text"]["format"]["name"] == "CriterionResult"


def test_registered_tool_is_run_and_tool_round_is_logged(tmp_path, monkeypatch):
    configure_test_paths(tmp_path, monkeypatch)
    function_call = SimpleNamespace(
        type="function_call",
        name="lookup_study",
        arguments='{"criterion_id":"C1"}',
        call_id="call_1",
        status="completed",
        id="fc_output_only_id",
    )
    client = FakeClient([response(text="", output=[function_call]), response("Found C1")])
    monkeypatch.setattr(llm, "create_client", lambda: client)
    handler_calls = []

    def lookup_study(criterion_id):
        handler_calls.append(criterion_id)
        return {"criterion_id": criterion_id, "text": "synthetic protocol rule"}

    tools = {
        "lookup_study": {
            "schema": {
                "type": "function",
                "name": "lookup_study",
                "description": "Look up one protocol criterion.",
                "parameters": {
                    "type": "object",
                    "properties": {"criterion_id": {"type": "string"}},
                    "required": ["criterion_id"],
                    "additionalProperties": False,
                },
            },
            "handler": lookup_study,
        }
    }

    result, usage = llm.call_agent(
        "protocol_agent",
        [{"role": "system", "content": "Fixed instructions."}, {"role": "user", "content": "Check C1."}],
        tools=tools,
    )

    assert result == "Found C1"
    assert handler_calls == ["C1"]
    assert usage["calls"] == 2
    assert usage["tool_calls"] == 1
    assert client.responses.requests[0]["tools"][0]["name"] == "lookup_study"
    echoed_call = client.responses.requests[1]["input"][-2]
    assert echoed_call == {
        "type": "function_call",
        "call_id": "call_1",
        "name": "lookup_study",
        "arguments": '{"criterion_id":"C1"}',
    }
    assert client.responses.requests[1]["input"][-1]["type"] == "function_call_output"


def test_screening_message_limit_logs_safety_and_blocks_api(tmp_path, monkeypatch):
    database, _, safety_log = configure_test_paths(tmp_path, monkeypatch)
    client = FakeClient([response()])
    monkeypatch.setattr(llm, "create_client", lambda: client)
    messages = [
        {"role": "system", "content": "Fixed screening prompt."},
        {"role": "user", "content": "x" * 801},
    ]

    with pytest.raises(BudgetExceeded) as error:
        llm.call_agent("candidate_screener", messages, candidate_id="synthetic-candidate")

    assert error.value.limit_name == "max_candidate_message_characters"
    assert client.responses.requests == []
    assert json.loads(safety_log.read_text(encoding="utf-8"))["limit"] == "max_candidate_message_characters"
    import sqlite3

    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM safety_events").fetchone()[0] == 1


def test_turn_cap_and_daily_budget_stop_calls(tmp_path, monkeypatch):
    limits = read_limits()
    limits["max_screening_turns_per_candidate"] = 1
    database, _, safety_log = configure_test_paths(tmp_path, monkeypatch, limits=limits)
    client = FakeClient([response(), response()])
    monkeypatch.setattr(llm, "create_client", lambda: client)
    messages = [
        {"role": "system", "content": "Fixed prompt."},
        {"role": "user", "content": "Synthetic candidate answer."},
    ]
    llm.call_agent("candidate_screener", messages, candidate_id="turn-limited")
    with pytest.raises(BudgetExceeded) as error:
        llm.call_agent("candidate_screener", messages, candidate_id="turn-limited")
    assert error.value.limit_name == "max_screening_turns_per_candidate"
    assert len(client.responses.requests) == 1
    assert json.loads(safety_log.read_text(encoding="utf-8").splitlines()[-1])["limit"] == "max_screening_turns_per_candidate"

    limits["daily_budget_usd"] = 0.000000001
    database, _, safety_log = configure_test_paths(tmp_path / "daily", monkeypatch, limits=limits)
    blocked_client = FakeClient([response()])
    monkeypatch.setattr(llm, "create_client", lambda: blocked_client)
    with pytest.raises(BudgetExceeded) as daily_error:
        llm.call_agent("demo_agent", [
            {"role": "system", "content": "Fixed system prompt."},
            {"role": "user", "content": "A tiny request."},
        ])
    assert daily_error.value.limit_name == "daily_budget_usd"
    assert blocked_client.responses.requests == []


def test_candidate_token_cap_blocks_before_call(tmp_path, monkeypatch):
    database, _, safety_log = configure_test_paths(tmp_path, monkeypatch)
    from eligibl.db import log_model_call

    log_model_call(database, {
        "agent": "prior_screener",
        "candidate_id": "token-limited",
        "run_id": "prior-run",
        "model": "gpt-6-luna",
        "input_tokens": 24_000,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "cost_usd": 0.0036,
        "latency_ms": 1,
        "outcome": "success",
    }, tmp_path / "prior.jsonl")
    client = FakeClient([response()])
    monkeypatch.setattr(llm, "create_client", lambda: client)

    with pytest.raises(BudgetExceeded) as error:
        llm.call_agent(
            "candidate_screener",
            [{"role": "system", "content": "Fixed prompt."}, {"role": "user", "content": "Continue."}],
            candidate_id="token-limited",
        )

    assert error.value.limit_name == "max_tokens_per_candidate"
    assert client.responses.requests == []
    assert json.loads(safety_log.read_text(encoding="utf-8"))["limit"] == "max_tokens_per_candidate"


def test_tool_loop_cap_blocks_handler_execution(tmp_path, monkeypatch):
    limits = read_limits()
    limits["max_tool_call_loops_per_agent_turn"] = 0
    configure_test_paths(tmp_path, monkeypatch, limits=limits)
    call = SimpleNamespace(type="function_call", name="safe_lookup", arguments="{}", call_id="call-x")
    client = FakeClient([response(text="", output=[call])])
    monkeypatch.setattr(llm, "create_client", lambda: client)
    handler_calls = []
    tools = {
        "safe_lookup": {
            "schema": {"type": "function", "name": "safe_lookup", "parameters": {"type": "object"}},
            "handler": lambda: handler_calls.append(True),
        }
    }

    with pytest.raises(BudgetExceeded) as error:
        llm.call_agent(
            "tool_agent",
            [{"role": "system", "content": "Fixed."}, {"role": "user", "content": "Look up."}],
            tools=tools,
        )

    assert error.value.limit_name == "max_tool_call_loops_per_agent_turn"
    assert handler_calls == []
    assert len(client.responses.requests) == 1


def test_retries_api_errors_at_most_twice_and_logs_each_attempt(tmp_path, monkeypatch):
    limits = read_limits()
    limits["max_api_retries"] = 9
    _, usage_log, _ = configure_test_paths(tmp_path, monkeypatch, limits=limits)
    api_error = APIError(
        "temporary",
        request=httpx.Request("POST", "https://api.portkey.ai/v1/responses"),
        body=None,
    )
    client = FakeClient([api_error, api_error, response()])
    monkeypatch.setattr(llm, "create_client", lambda: client)
    monkeypatch.setattr(llm.time, "sleep", lambda _seconds: None)

    result, usage = llm.call_agent("demo_agent", [
        {"role": "system", "content": "Stable test instructions."},
        {"role": "user", "content": "Reply with ok"},
    ])

    assert result == "ok"
    assert len(client.responses.requests) == 3
    assert usage["calls"] == 1
    assert usage["attempts"] == 3
    records = [json.loads(line) for line in usage_log.read_text(encoding="utf-8").splitlines()]
    assert [record["outcome"] for record in records] == ["error", "error", "success"]


def test_missing_cached_token_detail_defaults_to_zero():
    normalized = llm._usage({"usage": {"input_tokens": 42, "output_tokens": 7}})
    assert normalized == {"input": 42, "cached_input": 0, "output": 7}


def test_chat_style_usage_shape_can_supply_prompt_tokens_details():
    normalized = llm._usage({
        "usage": {
            "prompt_tokens": 42,
            "prompt_tokens_details": {"cached_tokens": 12},
            "output_tokens": 7,
        }
    })
    assert normalized == {"input": 42, "cached_input": 12, "output": 7}

"""Analytics aggregation, privacy boundary, and Insights route tests."""

import json
from datetime import UTC, datetime, timedelta

from eligibl.analytics import weekly_funnel_stats
from eligibl.config import REPO_ROOT
from eligibl.db import init_db


def _seed(database, *, old=False):
    init_db(database)
    now = datetime.now(UTC)
    completed = (now - timedelta(days=10 if old else 1)).isoformat()
    protocol = json.dumps({"criteria": [
        {"id": "C1", "requirement": "Does not work night shifts"},
        {"id": "C2", "requirement": "Is in the age range"},
    ]})
    with __import__("sqlite3").connect(database) as connection:
        for cid, decision, coordinator, contacted, status in [
            ("private-id-one", "Likely eligible", "approved", now.isoformat(), "completed"),
            ("private-id-two", "Not a match", "pending", None, "completed"),
            ("old-private-id", "Likely eligible", "approved", now.isoformat(), "completed"),
        ]:
            end = completed if cid != "old-private-id" or old else (now - timedelta(days=10)).isoformat()
            connection.execute("INSERT INTO candidates(id,created_at,display_name,decision_label,coordinator_status,contacted_at) VALUES(?,?,?,?,?,?)",
                               (cid, now.isoformat(), "Synthetic Private Name", decision, coordinator, contacted))
            connection.execute("INSERT INTO screening_sessions(candidate_id,consent_given,status,protocol_json,created_at,completed_at) VALUES(?,1,?,?,?,?)",
                               (cid, status, protocol, now.isoformat(), end))
            connection.execute("INSERT INTO screening_turns(candidate_id,turns,updated_at) VALUES(?,?,?)", (cid, 4, now.isoformat()))
            connection.execute("INSERT INTO model_call_logs(created_at,timestamp,agent,candidate_id,model,input_tokens,cached_input_tokens,output_tokens,cost_usd,latency_ms,outcome) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                               (now.isoformat(), now.isoformat(), "synthetic", cid, "gpt-6-luna", 100, 10, 20, 0.01, 3, "success"))
        connection.execute("INSERT INTO criterion_verdicts(candidate_id,criterion_id,verdict,created_at) VALUES('private-id-two','C1','not_met',?)", (now.isoformat(),))


def test_weekly_aggregates_funnel_failures_and_per_screening_metrics(tmp_path):
    database = str(tmp_path / "analytics.db")
    _seed(database)
    stats = weekly_funnel_stats(database, "UTC")

    assert [stage["count"] for stage in stats["funnel"]] == [2, 1, 1, 1]
    assert [stage["conversion_percent"] for stage in stats["funnel"]] == [100.0, 50.0, 100.0, 100.0]
    assert stats["why_not_a_match"] == [{"criterion_id": "C1", "label": "Does not work night shifts", "count": 1}]
    assert stats["screening_stats"] == {
        "completed_screenings": 2,
        "average_turns": 4.0,
        "average_tokens": 120.0,
        "average_cost_usd": 0.01,
    }
    serialized = json.dumps(stats)
    assert "private-id" not in serialized
    assert "Synthetic Private Name" not in serialized


def test_empty_analytics_returns_zero_counts_without_division_errors(tmp_path):
    database = str(tmp_path / "empty.db")
    init_db(database)
    stats = weekly_funnel_stats(database)
    assert [stage["count"] for stage in stats["funnel"]] == [0, 0, 0, 0]
    assert all(stage["conversion_percent"] == 0 for stage in stats["funnel"])
    assert stats["why_not_a_match"] == []
    assert stats["screening_stats"]["average_cost_usd"] == 0


def test_insights_agent_registers_only_aggregate_tool_and_validates_summary(tmp_path, monkeypatch):
    from eligibl.agents import insights

    database = str(tmp_path / "agent.db")
    _seed(database)
    observed = {}

    def fake_call(agent_name, messages, **kwargs):
        observed["agent"] = agent_name
        observed["tool_names"] = list(kwargs["tools"])
        observed["prompt"] = json.dumps(messages)
        observed["tool_result"] = kwargs["tools"]["get_funnel_stats"]["handler"]()
        return {"summary": "Two screenings completed this week, and one was marked likely eligible. One unmet criterion appeared once in the aggregate results. Consider reviewing the screening question for clarity before drawing conclusions."}, {"input": 22, "cached_input": 0, "output": 31, "tool_calls": 1}

    monkeypatch.setattr(insights, "call_agent", fake_call)
    result = insights.summarize_week(database)

    assert observed["agent"] == "weekly_insights"
    assert observed["tool_names"] == ["get_funnel_stats"]
    assert "private-id" not in observed["prompt"]
    assert "Synthetic Private Name" not in json.dumps(observed["tool_result"])
    assert len(result["summary"].split(".")) - 1 == 3


def test_insights_route_and_dashboard_analytics_markup(tmp_path, monkeypatch):
    from eligibl import create_app
    from eligibl.agents import insights

    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "route.db")})
    client = app.test_client()
    page = client.get("/coordinator")
    assert page.status_code == 200
    assert b"Summarize this week" in page.data
    assert b"analytics-fallback" in page.data
    assert b"chart.js" in page.data
    assert b"analytics.js?v=contrast-3" in page.data
    chart_source = (REPO_ROOT / "static" / "js" / "analytics.js").read_text(encoding="utf-8")
    assert 'color: "#514B46"' in chart_source
    assert '"#0F5F5C"' in chart_source and '"#B85C16"' in chart_source
    assert "scales.y.ticks.font = { size: 10, weight: 600 };" in chart_source
    assert "labels.map((item) => wrapLabel(item))" in chart_source
    assert "scales.y.ticks.autoSkip = false" in chart_source
    assert "chart-tall" in chart_source
    monkeypatch.setattr("eligibl.routes.main.api_key_found", lambda: True)
    monkeypatch.setattr(insights, "summarize_week", lambda database, timezone: {
        "summary": "The cohort is small this week. No dominant criterion failures appeared. Consider gathering more observations before changing operations.",
        "usage": {"input": 10, "output": 20},
    })
    response = client.post("/api/coordinator/insights/weekly")
    assert response.status_code == 200
    assert response.json["usage"]["output"] == 20


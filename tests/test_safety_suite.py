"""Integrated regression coverage for the complete safety scenario runner."""

from pathlib import Path

from eligibl import create_app
from eligibl.db import get_safety_events
from scripts.run_safety_tests import run_suite, write_results


def test_all_safety_scenarios_pass_and_appear_in_safety_dashboard(tmp_path: Path):
    safety_log = tmp_path / "logs" / "safety.jsonl"
    dashboard_database = tmp_path / "dashboard.sqlite3"
    outcomes = run_suite(
        root=tmp_path / "isolated-cases",
        safety_log=safety_log,
        dashboard_database=dashboard_database,
    )

    assert len(outcomes) == 10
    assert all(row["result"] == "PASS" for row in outcomes), outcomes
    assert safety_log.exists()
    assert "candidate_injection_flag" in safety_log.read_text(encoding="utf-8")
    event_types = {row["event"] for row in get_safety_events(dashboard_database)}
    assert {
        "candidate_injection_flag", "verifier_quote_missing", "medical_advice_redirect",
        "screening_turn_limit", "budget_limit_blocked", "rate_limit_blocked",
        "email_draft_blocked",
    } <= event_types

    app = create_app({"TESTING": True, "DATABASE": str(dashboard_database)})
    page = app.test_client().get("/coordinator/safety")
    assert page.status_code == 200
    assert b"candidate injection flag" in page.data.lower()
    report = tmp_path / "results.md"
    write_results(report, outcomes)
    assert "10/10 passed" in report.read_text(encoding="utf-8")

"""Tests for the idempotent, no-API synthetic dashboard seeder."""

from eligibl.db import candidate_totals, coordinator_candidates, get_candidate_messages
from eligibl import create_app
from scripts.seed_demo_dashboard import seed_demo_dashboard


def test_demo_seed_populates_finished_personas_once_without_model_usage(tmp_path):
    database = tmp_path / "demo.sqlite3"
    safety_log = tmp_path / "safety.jsonl"

    first = seed_demo_dashboard(database, safety_log=safety_log)
    second = seed_demo_dashboard(database, safety_log=safety_log)

    assert first == {
        "added": 24,
        "skipped": 0,
        "total": 24,
        "statuses": {
            "Flagged": 3,
            "Needs review": 14,
            "Not a match": 7,
        },
    }
    assert second["added"] == 0
    assert second["skipped"] == 24
    rows = [row for row in coordinator_candidates(database) if row["id"].startswith("demo-SYN")]
    assert all(row["session_status"] == "completed" for row in rows)
    assert all(candidate_totals(database, row["id"])["tokens"] == 0 for row in rows)
    assert any("no real participant" in row["verifier_summary"].lower() for row in rows)
    assert len(get_candidate_messages(database, "demo-SYN023")) > 10
    assert len(safety_log.read_text(encoding="utf-8").splitlines()) == 3
    app = create_app({"TESTING": True, "DATABASE": str(database)})
    dashboard = app.test_client().get("/coordinator")
    assert dashboard.status_code == 200
    assert b"24 synthetic demo screenings" in dashboard.data
    assert b"no real participants or live model calls" in dashboard.data

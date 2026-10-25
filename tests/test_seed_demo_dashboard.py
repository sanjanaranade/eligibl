"""Tests for the idempotent, no-API synthetic dashboard seeder."""

import json

from eligibl.db import (
    candidate_totals,
    coordinator_candidates,
    create_candidate_screening,
    get_candidate_messages,
    get_email_drafts,
    init_db,
)
from eligibl import create_app
from eligibl.config import REPO_ROOT
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


def test_fresh_normal_app_startup_seeds_24_approved_examples_and_unsent_drafts(tmp_path):
    database = tmp_path / "fresh.sqlite3"
    safety_log = tmp_path / "safety.jsonl"

    app = create_app({
        "DATABASE": str(database),
        "DEMO_SAFETY_LOG": str(safety_log),
    })

    candidates = coordinator_candidates(database)
    approved = [row for row in candidates if row["coordinator_status"] == "approved"]
    drafts = get_email_drafts(database)
    assert len(candidates) == 24
    assert len(approved) == 3
    assert len(drafts) == 9
    assert all(draft["status"] == "draft" for draft in drafts)
    assert all(draft["queued_at"] is None and draft["sent_at"] is None for draft in drafts)
    assert app.test_client().get("/coordinator").status_code == 200


def test_normal_app_startup_preserves_nonempty_database(tmp_path):
    database = tmp_path / "existing.sqlite3"
    safety_log = tmp_path / "safety.jsonl"
    protocol = json.loads(
        (REPO_ROOT / "data" / "protocol.json").read_text(encoding="utf-8")
    )
    init_db(database)
    create_candidate_screening(database, "keep-this-record", "Taylor", protocol)

    create_app({"DATABASE": str(database), "DEMO_SAFETY_LOG": str(safety_log)})

    candidates = coordinator_candidates(database)
    assert [row["id"] for row in candidates] == ["keep-this-record"]
    assert get_email_drafts(database) == []
    assert not safety_log.exists()


def test_test_app_factory_does_not_implicitly_seed(tmp_path):
    database = tmp_path / "test-mode.sqlite3"

    create_app({"TESTING": True, "DATABASE": str(database)})

    assert coordinator_candidates(database) == []

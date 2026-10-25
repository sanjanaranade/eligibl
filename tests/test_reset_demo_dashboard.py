"""Safe reset, preservation, and coordinator mockup seed tests."""

import json
import sqlite3

from eligibl.db import (
    coordinator_candidates,
    create_candidate_screening,
    get_candidate_messages,
    get_email_drafts,
    init_db,
    save_candidate_message,
)
from eligibl.config import REPO_ROOT
from scripts.reset_demo_dashboard import reset_and_seed_demo_dashboard


def test_reset_backs_up_old_participant_data_and_seeds_approved_unsent_examples(tmp_path):
    database = tmp_path / "app.sqlite3"
    backup_dir = tmp_path / "backups"
    safety_log = tmp_path / "safety.jsonl"
    protocol = json.loads((REPO_ROOT / "data" / "protocol.json").read_text(encoding="utf-8"))
    init_db(database)
    create_candidate_screening(database, "old-participant", "Rajesh", protocol)
    save_candidate_message(database, "old-participant", "user", "old synthetic reply")
    with sqlite3.connect(database) as connection:
        connection.execute(
            """INSERT INTO model_call_logs(created_at,agent,model,input_tokens,cached_input_tokens,
                      output_tokens,cost_usd,latency_ms,outcome) VALUES(?,?,?,?,?,?,?,?,?)""",
            ("2026-10-24T12:00:00+00:00", "candidate_screener", "gpt-6-luna", 40, 10, 20, 0.02, 30, "success"),
        )
        connection.execute(
            "INSERT INTO safety_events(timestamp,event,limit_name,details_json) VALUES(?,?,?,?)",
            ("2026-10-24T12:00:00+00:00", "global_test_event", "test", "{}"),
        )

    result = reset_and_seed_demo_dashboard(database, backup_dir=backup_dir, safety_log=safety_log)

    backup = result["backup"]
    assert backup is not None
    with sqlite3.connect(backup) as connection:
        assert connection.execute("SELECT count(*) FROM candidates").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM model_call_logs").fetchone()[0] == 1
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT count(*) FROM candidates").fetchone()[0] == 24
        assert connection.execute("SELECT count(*) FROM model_call_logs").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM safety_events WHERE event='global_test_event'").fetchone()[0] == 1

    candidates = coordinator_candidates(database)
    approved = [row for row in candidates if row["coordinator_status"] == "approved"]
    assert len(approved) == 3
    assert all(row["decision_label"] == "Likely eligible" for row in approved)
    assert any("synthetic dashboard mockup only" in row["override_reason"].lower() for row in approved)
    assert all(get_candidate_messages(database, row["id"]) for row in candidates)
    assert result["drafts"] == 9
    drafts = get_email_drafts(database)
    assert len(drafts) == 9
    assert all(row["status"] == "draft" and row["approval_status"] == "draft" for row in drafts)
    assert all(row["queued_at"] is None and row["sent_at"] is None for row in drafts)
    assert result["queued"] == 0
    assert len([row for row in candidates if row["id"].startswith("demo-SYN")]) == 24

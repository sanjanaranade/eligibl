"""Back up local participant data, then preload a synthetic coordinator mockup."""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from eligibl import db
from eligibl.agents import outreach
from eligibl.config import REPO_ROOT
from eligibl.llm import DEFAULT_DATABASE
from scripts.seed_demo_dashboard import PERSONAS_PATH, PROTOCOL_PATH, SAFETY_LOG_PATH, seed_demo_dashboard


BACKUP_DIR = REPO_ROOT / "data" / "backups"
APPROVED_DEMO_COUNT = 3
DEMO_OVERRIDE_REASON = (
    "Synthetic dashboard mockup only: for these fictional records, clinic-only criteria are "
    "assumed confirmed solely to demonstrate coordinator approval and draft outreach."
)


def backup_database(database: str | Path, backup_dir: str | Path = BACKUP_DIR) -> Path | None:
    """Create a consistent SQLite backup before changing participant data."""
    source_path = Path(database)
    if not source_path.exists():
        return None
    folder = Path(backup_dir)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = folder / f"eligibl-before-demo-reset-{stamp}.sqlite3"
    source = sqlite3.connect(source_path, timeout=10)
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    return destination


def clear_participant_records(database: str | Path) -> None:
    """Remove candidate-linked app state while preserving model cost history."""
    db.init_db(database)
    with db.session(database) as connection:
        for table in (
            "email_drafts",
            "coordinator_actions",
            "candidate_concerns",
            "criterion_verdicts",
            "candidate_messages",
            "screening_sessions",
            "screening_turns",
            "screening_rate_events",
            "candidates",
        ):
            connection.execute(f"DELETE FROM {table}")
        connection.execute("DELETE FROM agent_trace_steps WHERE candidate_id IS NOT NULL")
        connection.execute("DELETE FROM safety_events WHERE candidate_id IS NOT NULL")


def _sample_drafts(database: str | Path, candidate_id: str) -> list[dict[str, Any]]:
    """Build validated, clearly synthetic draft examples without model calls."""
    summary = outreach.get_candidate_summary(database, candidate_id, status_override="Approved")
    slots = outreach.get_available_slots()
    chosen_slot = summary["chosen_slot"]
    greeting = f"Hello {summary['first_name']},"
    contact = json.loads(outreach.AVAILABILITY_PATH.read_text(encoding="utf-8"))["study_team_contact_line"]
    options = "\n".join(f"• {slot['label']}" for slot in slots)
    common = "Participation is voluntary; you may decide whether taking part is right for you.\n\n" + contact
    invitation_body = (
        f"{greeting}\n\nThe study team would like to invite you to an intake visit for "
        f"{summary['study_title']}. Please choose from these proposed times:\n{options}\n\n{common}"
    )
    reminders = [
        {
            "type": "invitation",
            "subject": "Invitation to schedule a study visit",
            "body": invitation_body,
            "send_at": outreach._schedule(summary, "invitation"),
        },
        {
            "type": "reminder_2_days",
            "subject": "A reminder about your upcoming study visit",
            "body": f"{greeting}\n\nThis is a reminder that your intake visit is scheduled for {chosen_slot}.\n\n{common}",
            "send_at": outreach._schedule(summary, "reminder_2_days"),
        },
        {
            "type": "reminder_morning_of",
            "subject": "Your study visit is today",
            "body": f"{greeting}\n\nThis is a reminder that your intake visit is scheduled for {chosen_slot}.\n\n{common}",
            "send_at": outreach._schedule(summary, "reminder_morning_of"),
        },
    ]
    for draft in reminders:
        outreach.validate_draft(draft["type"], draft["subject"], draft["body"], chosen_slot)
    return reminders


def reset_and_seed_demo_dashboard(
    database: str | Path = DEFAULT_DATABASE,
    *,
    backup_dir: str | Path = BACKUP_DIR,
    personas_path: str | Path = PERSONAS_PATH,
    protocol_path: str | Path = PROTOCOL_PATH,
    safety_log: str | Path = SAFETY_LOG_PATH,
) -> dict[str, Any]:
    """Back up, clear participant-linked records, and seed 24 synthetic profiles.

    Model-call cost records are retained. Three clearly eligible personas receive
    coordinator override/approval examples and unqueued, unsent sample email drafts.
    """
    backup = backup_database(database, backup_dir)
    clear_participant_records(database)
    seeded = seed_demo_dashboard(
        database,
        personas_path=personas_path,
        protocol_path=protocol_path,
        safety_log=safety_log,
    )
    protocol = json.loads(Path(protocol_path).read_text(encoding="utf-8"))
    personas = json.loads(Path(personas_path).read_text(encoding="utf-8"))
    eligible = [persona for persona in personas if persona.get("planned_outcome") == "clearly_eligible"]
    if len(eligible) < APPROVED_DEMO_COUNT:
        raise ValueError("The synthetic persona bank has too few clearly eligible demo candidates.")

    created_drafts = 0
    for index, persona in enumerate(eligible[:APPROVED_DEMO_COUNT]):
        candidate_id = f"demo-{persona['id']}"
        slot = outreach.get_available_slots()[index % len(outreach.get_available_slots())]
        db.record_coordinator_action(
            database,
            candidate_id,
            "override",
            reason=DEMO_OVERRIDE_REASON,
            target_label="Likely eligible",
        )
        db.set_candidate_chosen_slot(database, candidate_id, slot["label"])
        drafts = _sample_drafts(database, candidate_id)
        db.insert_email_drafts(database, candidate_id, drafts)
        db.record_coordinator_action(database, candidate_id, "approve")
        # Keep the synthetic-only override disclosure visible after approval.
        with db.session(database) as connection:
            connection.execute(
                "UPDATE candidates SET override_reason=? WHERE id=?",
                (DEMO_OVERRIDE_REASON, candidate_id),
            )
        created_drafts += len(drafts)

    candidates = db.coordinator_candidates(database)
    demo_rows = [row for row in candidates if row["id"].startswith("demo-SYN")]
    statuses: dict[str, int] = {}
    for row in demo_rows:
        statuses[row["display_status"]] = statuses.get(row["display_status"], 0) + 1
    return {
        "backup": str(backup) if backup else None,
        "added": seeded["added"],
        "total": len(demo_rows),
        "approved": sum(row["coordinator_status"] == "approved" for row in demo_rows),
        "drafts": created_drafts,
        "queued": sum(draft["status"] == "queued" for draft in db.get_email_drafts(database)),
        "statuses": dict(sorted(statuses.items())),
    }


def main() -> None:
    """Run the local backup-and-reset flow and print a compact audit summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--backup-dir", type=Path, default=BACKUP_DIR)
    parser.add_argument("--safety-log", type=Path, default=SAFETY_LOG_PATH)
    args = parser.parse_args()
    result = reset_and_seed_demo_dashboard(
        args.database, backup_dir=args.backup_dir, safety_log=args.safety_log
    )
    print(f"Backup: {result['backup']}")
    print(f"Synthetic candidates: {result['total']} | coordinator-approved: {result['approved']}")
    print(f"Email drafts: {result['drafts']} | queued/sent: {result['queued']}/0")
    print(f"Statuses: {json.dumps(result['statuses'], sort_keys=True)}")
    print("Model cost records were preserved; no API calls or emails were sent.")


if __name__ == "__main__":
    main()

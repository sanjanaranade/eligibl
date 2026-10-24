"""SQLite helpers for synthetic candidates, reviews, and model-call metrics."""

from __future__ import annotations

import sqlite3
import json
from contextlib import contextmanager
from datetime import UTC, datetime, time as datetime_time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    display_name TEXT NOT NULL,
    screening_result TEXT NOT NULL DEFAULT 'pending'
        CHECK (screening_result IN ('pending', 'potentially_eligible', 'not_eligible', 'uncertain')),
    coordinator_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (coordinator_status IN ('pending', 'approved', 'rejected')),
    decision_label TEXT NOT NULL DEFAULT 'Needs review',
    verifier_summary TEXT NOT NULL DEFAULT '',
    verifier_status TEXT NOT NULL DEFAULT 'pending',
    override_reason TEXT NOT NULL DEFAULT '',
    contacted_at TEXT,
    chosen_slot TEXT
);
CREATE TABLE IF NOT EXISTS screening_sessions (
    candidate_id TEXT PRIMARY KEY REFERENCES candidates(id),
    consent_given INTEGER NOT NULL CHECK (consent_given IN (0, 1)),
    status TEXT NOT NULL DEFAULT 'in_progress'
        CHECK (status IN ('in_progress', 'completed', 'turn_limit')),
    protocol_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE TABLE IF NOT EXISTS candidate_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL REFERENCES candidates(id),
    role TEXT NOT NULL CHECK (role IN ('assistant', 'user')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS candidate_concerns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL REFERENCES candidates(id),
    reason TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS coordinator_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL REFERENCES candidates(id),
    action TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS criterion_verdicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL REFERENCES candidates(id),
    criterion_id TEXT NOT NULL,
    verdict TEXT NOT NULL CHECK (verdict IN ('met', 'not_met', 'unknown')),
    evidence_quote TEXT NOT NULL DEFAULT '',
    rationale TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS email_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL REFERENCES candidates(id),
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    draft_type TEXT NOT NULL DEFAULT 'custom',
    send_at TEXT,
    queued_at TEXT,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'queued', 'rejected')),
    approval_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (approval_status IN ('draft', 'approved', 'rejected')),
    sent_at TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS model_call_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    created_at TEXT NOT NULL,
    agent TEXT NOT NULL,
    candidate_id TEXT,
    run_id TEXT,
    model TEXT NOT NULL,
    input_tokens INTEGER,
    cached_input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd REAL,
    latency_ms REAL NOT NULL,
    outcome TEXT NOT NULL,
    error_type TEXT
);
CREATE TABLE IF NOT EXISTS agent_trace_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    candidate_id TEXT,
    step_number INTEGER NOT NULL,
    agent TEXT NOT NULL,
    input_summary TEXT NOT NULL,
    tool_calls_json TEXT NOT NULL,
    output_summary TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    cached_input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    timestamp TEXT NOT NULL,
    UNIQUE(run_id, step_number)
);
CREATE TABLE IF NOT EXISTS screening_turns (
    candidate_id TEXT PRIMARY KEY,
    turns INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS safety_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    event TEXT NOT NULL,
    agent TEXT,
    candidate_id TEXT,
    run_id TEXT,
    limit_name TEXT NOT NULL,
    details_json TEXT NOT NULL
);
"""


def connect(database: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with row access and foreign keys enabled."""
    path = Path(database)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


@contextmanager
def session(database: str | Path):
    """Yield a SQLite connection and always close it after the transaction."""
    connection = connect(database)
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db(database: str | Path) -> None:
    """Create the application's tables if they do not already exist."""
    with session(database) as connection:
        connection.executescript(SCHEMA)
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(model_call_logs)")
        }
        if "timestamp" not in columns:
            connection.execute("ALTER TABLE model_call_logs ADD COLUMN timestamp TEXT")
            connection.execute("UPDATE model_call_logs SET timestamp = created_at WHERE timestamp IS NULL")
        if "run_id" not in columns:
            connection.execute("ALTER TABLE model_call_logs ADD COLUMN run_id TEXT")
        candidate_columns = {row["name"] for row in connection.execute("PRAGMA table_info(candidates)")}
        migrations = {
            "decision_label": "TEXT NOT NULL DEFAULT 'Needs review'",
            "verifier_summary": "TEXT NOT NULL DEFAULT ''",
            "verifier_status": "TEXT NOT NULL DEFAULT 'pending'",
            "override_reason": "TEXT NOT NULL DEFAULT ''",
            "contacted_at": "TEXT",
            "chosen_slot": "TEXT",
        }
        for name, declaration in migrations.items():
            if name not in candidate_columns:
                connection.execute(f"ALTER TABLE candidates ADD COLUMN {name} {declaration}")
        draft_columns = {row["name"] for row in connection.execute("PRAGMA table_info(email_drafts)")}
        draft_migrations = {
            "draft_type": "TEXT NOT NULL DEFAULT 'custom'",
            "send_at": "TEXT",
            "queued_at": "TEXT",
            "status": "TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'queued', 'rejected'))",
        }
        for name, declaration in draft_migrations.items():
            if name not in draft_columns:
                connection.execute(f"ALTER TABLE email_drafts ADD COLUMN {name} {declaration}")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_model_calls_timestamp ON model_call_logs(timestamp)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_model_calls_candidate ON model_call_logs(candidate_id)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_candidate_messages_candidate ON candidate_messages(candidate_id, id)"
        )


def append_jsonl(path: str | Path, record: dict[str, Any]) -> None:
    """Append one compact JSON record without storing prompts or key values."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")


def log_model_call(database: str | Path, record: dict[str, Any], log_path: str | Path) -> None:
    """Persist one call's accounting fields to SQLite and append-only JSONL."""
    timestamp = record.get("timestamp") or datetime.now(UTC).isoformat()
    values = (
        timestamp,
        timestamp,
        record["agent"],
        record.get("candidate_id"),
        record.get("run_id"),
        record.get("model", "gpt-6-luna"),
        record.get("input_tokens"),
        record.get("cached_input_tokens"),
        record.get("output_tokens"),
        record.get("cost_usd"),
        record["latency_ms"],
        record["outcome"],
        record.get("error_type"),
    )
    with session(database) as connection:
        connection.execute(
            """INSERT INTO model_call_logs (
                timestamp, created_at, agent, candidate_id, run_id, model, input_tokens,
                cached_input_tokens, output_tokens, cost_usd, latency_ms,
                outcome, error_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            values,
        )
    line = {
        "timestamp": timestamp,
        "agent": record["agent"],
        "candidate_id": record.get("candidate_id"),
        "run_id": record.get("run_id"),
        "input": record.get("input_tokens", 0),
        "cached_input": record.get("cached_input_tokens", 0),
        "output": record.get("output_tokens", 0),
        "cost_usd": record.get("cost_usd"),
        "latency_ms": round(float(record["latency_ms"]), 3),
        "model": record.get("model", "gpt-6-luna"),
        "outcome": record["outcome"],
    }
    if record.get("error_type"):
        line["error_type"] = record["error_type"]
    append_jsonl(log_path, line)


def candidate_totals(database: str | Path, candidate_id: str) -> dict[str, int]:
    """Return cumulative token use and screening turns for a candidate."""
    with session(database) as connection:
        row = connection.execute(
            """SELECT COALESCE(SUM(COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)), 0) AS tokens,
                      COALESCE(SUM(COALESCE(input_tokens, 0)), 0) AS input_tokens,
                      COALESCE(SUM(COALESCE(cached_input_tokens, 0)), 0) AS cached_input_tokens,
                      COALESCE(SUM(COALESCE(output_tokens, 0)), 0) AS output_tokens
               FROM model_call_logs WHERE candidate_id = ?""",
            (candidate_id,),
        ).fetchone()
        turn = connection.execute(
            "SELECT turns FROM screening_turns WHERE candidate_id = ?", (candidate_id,)
        ).fetchone()
    totals = dict(row)
    totals["turns"] = int(turn["turns"]) if turn else 0
    return {key: int(value or 0) for key, value in totals.items()}


def reserve_screening_turn(database: str | Path, candidate_id: str, maximum: int) -> int | None:
    """Atomically reserve a candidate screening turn; return None at the limit."""
    now = datetime.now(UTC).isoformat()
    with session(database) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT turns FROM screening_turns WHERE candidate_id = ?", (candidate_id,)
        ).fetchone()
        current = int(row["turns"]) if row else 0
        if current >= maximum:
            return None
        new_value = current + 1
        connection.execute(
            """INSERT INTO screening_turns(candidate_id, turns, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(candidate_id) DO UPDATE SET turns = excluded.turns, updated_at = excluded.updated_at""",
            (candidate_id, new_value, now),
        )
    return new_value


def usage_totals_today(database: str | Path, timezone_name: str) -> dict[str, Any]:
    """Aggregate token and estimated-cost usage for today's configured timezone."""
    zone = ZoneInfo(timezone_name)
    local_now = datetime.now(zone)
    start_local = datetime.combine(local_now.date(), datetime_time.min, tzinfo=zone)
    end_local = start_local + timedelta(days=1)
    start_utc = start_local.astimezone(UTC).isoformat()
    end_utc = end_local.astimezone(UTC).isoformat()
    with session(database) as connection:
        row = connection.execute(
            """SELECT COUNT(*) AS calls,
                      COALESCE(SUM(COALESCE(input_tokens, 0)), 0) AS input_tokens,
                      COALESCE(SUM(COALESCE(cached_input_tokens, 0)), 0) AS cached_input_tokens,
                      COALESCE(SUM(COALESCE(output_tokens, 0)), 0) AS output_tokens,
                      COALESCE(SUM(COALESCE(cost_usd, 0)), 0.0) AS cost_usd
               FROM model_call_logs WHERE timestamp >= ? AND timestamp < ?""",
            (start_utc, end_utc),
        ).fetchone()
    return {**dict(row), "date": local_now.date().isoformat(), "timezone": timezone_name}


def create_candidate_screening(
    database: str | Path,
    candidate_id: str,
    first_name: str,
    protocol: dict[str, Any],
) -> None:
    """Create a synthetic candidate and persist the protocol snapshot they saw."""
    now = datetime.now(UTC).isoformat()
    with session(database) as connection:
        connection.execute(
            "INSERT INTO candidates(id, created_at, display_name) VALUES (?, ?, ?)",
            (candidate_id, now, first_name),
        )
        connection.execute(
            """INSERT INTO screening_sessions(candidate_id, consent_given, protocol_json, created_at)
               VALUES (?, 1, ?, ?)""",
            (candidate_id, json.dumps(protocol, ensure_ascii=False), now),
        )


def get_screening_session(database: str | Path, candidate_id: str) -> dict[str, Any] | None:
    """Return a candidate's screening session without exposing other sessions."""
    with session(database) as connection:
        row = connection.execute(
            """SELECT c.id, c.display_name, s.consent_given, s.status, s.protocol_json,
                      s.created_at, s.completed_at
               FROM candidates AS c JOIN screening_sessions AS s ON s.candidate_id = c.id
               WHERE c.id = ?""",
            (candidate_id,),
        ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["protocol"] = json.loads(result.pop("protocol_json"))
    return result


def save_candidate_message(
    database: str | Path,
    candidate_id: str,
    role: str,
    content: str,
) -> None:
    """Append one candidate or assistant message to the persisted chat."""
    if role not in {"user", "assistant"}:
        raise ValueError("Chat role must be user or assistant.")
    with session(database) as connection:
        connection.execute(
            "INSERT INTO candidate_messages(candidate_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (candidate_id, role, content, datetime.now(UTC).isoformat()),
        )


def get_candidate_messages(database: str | Path, candidate_id: str) -> list[dict[str, str]]:
    """Return ordered chat messages for one candidate session."""
    with session(database) as connection:
        rows = connection.execute(
            "SELECT role, content, created_at FROM candidate_messages WHERE candidate_id = ? ORDER BY id",
            (candidate_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def recorded_criterion_ids(database: str | Path, candidate_id: str) -> set[str]:
    """Return criteria with a saved screening verdict for this candidate."""
    with session(database) as connection:
        rows = connection.execute(
            "SELECT DISTINCT criterion_id FROM criterion_verdicts WHERE candidate_id = ?",
            (candidate_id,),
        ).fetchall()
    return {row["criterion_id"] for row in rows}


def save_criterion_answer(
    database: str | Path,
    candidate_id: str,
    criterion_id: str,
    verdict: str,
    evidence_quote: str,
    note: str,
) -> None:
    """Persist one criterion assessment, mapping screener labels to storage labels."""
    verdict_map = {"satisfied": "met", "not_satisfied": "not_met", "unclear": "unknown"}
    if verdict not in verdict_map:
        raise ValueError("Invalid candidate criterion verdict.")
    with session(database) as connection:
        existing = connection.execute(
            "SELECT id FROM criterion_verdicts WHERE candidate_id = ? AND criterion_id = ? ORDER BY id DESC LIMIT 1",
            (candidate_id, criterion_id),
        ).fetchone()
        if existing:
            connection.execute(
                "UPDATE criterion_verdicts SET verdict = ?, evidence_quote = ?, rationale = ?, created_at = ? WHERE id = ?",
                (verdict_map[verdict], evidence_quote, note, datetime.now(UTC).isoformat(), existing["id"]),
            )
        else:
            connection.execute(
                """INSERT INTO criterion_verdicts(candidate_id, criterion_id, verdict, evidence_quote, rationale, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (candidate_id, criterion_id, verdict_map[verdict], evidence_quote, note, datetime.now(UTC).isoformat()),
            )


def get_criterion_answers(database: str | Path, candidate_id: str) -> list[dict[str, Any]]:
    """Return the saved criterion answers for coordinator review and tests."""
    with session(database) as connection:
        rows = connection.execute(
            """SELECT criterion_id, verdict, evidence_quote, rationale AS note, created_at
               FROM criterion_verdicts WHERE candidate_id = ? ORDER BY id""",
            (candidate_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def save_candidate_concern(database: str | Path, candidate_id: str, reason: str) -> None:
    """Store a coordinator-visible concern raised during a synthetic chat."""
    with session(database) as connection:
        connection.execute(
            "INSERT INTO candidate_concerns(candidate_id, reason, created_at) VALUES (?, ?, ?)",
            (candidate_id, reason[:500], datetime.now(UTC).isoformat()),
        )


def set_screening_status(database: str | Path, candidate_id: str, status: str) -> None:
    """Set the chat lifecycle status; this does not decide candidate eligibility."""
    if status not in {"in_progress", "completed", "turn_limit"}:
        raise ValueError("Invalid screening lifecycle status.")
    completed_at = datetime.now(UTC).isoformat() if status != "in_progress" else None
    with session(database) as connection:
        connection.execute(
            "UPDATE screening_sessions SET status = ?, completed_at = ? WHERE candidate_id = ?",
            (status, completed_at, candidate_id),
        )


def save_verification(database: str | Path, candidate_id: str, summary: str, status: str) -> None:
    """Persist verifier output/status and the code-computed decision label."""
    from .decision import classify_candidate

    session_data = get_screening_session(database, candidate_id)
    if session_data is None:
        raise LookupError("Candidate not found.")
    answers = get_criterion_answers(database, candidate_id)
    concerns = get_candidate_concerns(database, candidate_id)
    flags = has_injection_flag(database, candidate_id)
    decision = classify_candidate(
        [row for row in answers],
        concerns=concerns,
        injection_flag=flags,
        required_criteria=[row["id"] for row in session_data["protocol"]["criteria"] if not row["requires_clinic_check"]],
        verification_complete=status == "complete",
    )
    with session(database) as connection:
        connection.execute(
            "UPDATE candidates SET verifier_summary = ?, verifier_status = ?, decision_label = ? WHERE id = ?",
            (summary[:1000], status, decision, candidate_id),
        )


def get_candidate_concerns(database: str | Path, candidate_id: str) -> list[dict[str, Any]]:
    """Return explicitly raised coordinator review concerns for one candidate."""
    with session(database) as connection:
        rows = connection.execute(
            "SELECT reason, created_at FROM candidate_concerns WHERE candidate_id = ? ORDER BY id",
            (candidate_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def flag_injection(
    database: str | Path, candidate_id: str, reason: str, log_path: str | Path | None = None
) -> None:
    """Record a detected candidate prompt-injection attempt for coordinator review."""
    save_candidate_concern(database, candidate_id, "Possible prompt injection: " + reason[:400])
    record_safety_event(
        database, log_path or Path(__file__).resolve().parents[1] / "logs" / "safety.jsonl",
        event="candidate_injection_flag", limit_name="prompt_injection",
        details={"reason": reason[:400]}, agent="candidate_screener", candidate_id=candidate_id,
    )


def has_injection_flag(database: str | Path, candidate_id: str) -> bool:
    """Return whether a candidate has a recorded prompt-injection flag."""
    with session(database) as connection:
        row = connection.execute(
            "SELECT 1 FROM safety_events WHERE candidate_id = ? AND event = 'candidate_injection_flag' LIMIT 1",
            (candidate_id,),
        ).fetchone()
    return row is not None


def record_coordinator_action(
    database: str | Path, candidate_id: str, action: str, reason: str = "", target_label: str = ""
) -> None:
    """Append a timestamped coordinator action and update review state."""
    now = datetime.now(UTC).isoformat()
    with session(database) as connection:
        if action == "approve":
            connection.execute("UPDATE candidates SET coordinator_status='approved', override_reason='' WHERE id=?", (candidate_id,))
        elif action == "mark_not_match":
            connection.execute("UPDATE candidates SET coordinator_status='rejected', decision_label='Not a match' WHERE id=?", (candidate_id,))
        elif action == "override":
            allowed = {"Flagged", "Not a match", "Needs review", "Likely eligible"}
            if target_label not in allowed or not reason.strip():
                raise ValueError("Choose a valid decision and provide an override reason.")
            connection.execute("UPDATE candidates SET decision_label=?, override_reason=? WHERE id=?", (target_label, reason[:1000], candidate_id))
        elif action == "contacted":
            connection.execute("UPDATE candidates SET contacted_at=? WHERE id=?", (now, candidate_id))
        else:
            raise ValueError("Unsupported coordinator action.")
        connection.execute(
            "INSERT INTO coordinator_actions(candidate_id,action,reason,created_at) VALUES(?,?,?,?)",
            (candidate_id, action, reason[:1000], now),
        )


def coordinator_candidates(database: str | Path) -> list[dict[str, Any]]:
    """Return candidates and compact review metrics for the coordinator table."""
    with session(database) as connection:
        rows = connection.execute(
            """SELECT c.*, s.status AS session_status, s.protocol_json, s.created_at AS screening_started,
                      s.completed_at,
                      (SELECT COUNT(*) FROM criterion_verdicts v WHERE v.candidate_id=c.id AND v.verdict='met') AS criteria_met,
                      (SELECT COUNT(*) FROM criterion_verdicts v WHERE v.candidate_id=c.id) AS criteria_answered,
                      (SELECT COALESCE(SUM(l.input_tokens+l.output_tokens),0) FROM model_call_logs l WHERE l.candidate_id=c.id) AS total_tokens,
                      (SELECT COALESCE(SUM(l.cost_usd),0) FROM model_call_logs l WHERE l.candidate_id=c.id) AS total_cost,
                      EXISTS(SELECT 1 FROM candidate_concerns x WHERE x.candidate_id=c.id) AS has_concern,
                      EXISTS(SELECT 1 FROM safety_events e WHERE e.candidate_id=c.id AND e.event='candidate_injection_flag') AS injection_flag
               FROM candidates c LEFT JOIN screening_sessions s ON s.candidate_id=c.id ORDER BY c.created_at DESC"""
        ).fetchall()
    results = []
    for row in rows:
        item = dict(row)
        protocol = json.loads(item.pop("protocol_json") or "{}")
        item["criteria_total"] = sum(not criterion.get("requires_clinic_check", False) for criterion in protocol.get("criteria", []))
        flagged = bool(item["has_concern"] or item["injection_flag"])
        if flagged and not item["override_reason"]:
            item["decision_label"] = "Flagged"
        item["display_status"] = (
            item["decision_label"]
            if item["session_status"] == "completed" or flagged or item["override_reason"]
            else "In progress"
        )
        results.append(item)
    return results


def get_safety_events(database: str | Path) -> list[dict[str, Any]]:
    """Return safety events with decoded, secret-free details for the coordinator."""
    with session(database) as connection:
        rows = connection.execute(
            "SELECT timestamp,event,agent,candidate_id,limit_name,details_json FROM safety_events ORDER BY id DESC LIMIT 200"
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["details"] = json.loads(item.pop("details_json"))
        result.append(item)
    return result


def coordinator_detail(database: str | Path, candidate_id: str) -> dict[str, Any] | None:
    """Gather one candidate's evidence, transcript, trace, costs, and actions."""
    candidates = coordinator_candidates(database)
    candidate = next((row for row in candidates if row["id"] == candidate_id), None)
    if candidate is None:
        return None
    session_data = get_screening_session(database, candidate_id)
    criteria = session_data["protocol"]["criteria"] if session_data else []
    answers = {row["criterion_id"]: row for row in get_criterion_answers(database, candidate_id)}
    with session(database) as connection:
        actions = [dict(row) for row in connection.execute(
            "SELECT action, reason, created_at FROM coordinator_actions WHERE candidate_id=? ORDER BY id", (candidate_id,)
        )]
        traces = [dict(row) for row in connection.execute(
            "SELECT run_id,step_number,agent,input_summary,tool_calls_json,output_summary,input_tokens,cached_input_tokens,output_tokens,timestamp FROM agent_trace_steps WHERE candidate_id=? ORDER BY timestamp,step_number", (candidate_id,)
        )]
        usages = [dict(row) for row in connection.execute(
            "SELECT input_tokens,cached_input_tokens,output_tokens,cost_usd,latency_ms,agent,timestamp FROM model_call_logs WHERE candidate_id=? ORDER BY timestamp", (candidate_id,)
        )]
    for trace in traces:
        trace["tool_calls"] = json.loads(trace.pop("tool_calls_json"))
    candidate.update(
        criteria=[{**criterion, "answer": answers.get(criterion["id"])} for criterion in criteria],
        transcript=get_candidate_messages(database, candidate_id),
        concerns=get_candidate_concerns(database, candidate_id),
        actions=actions,
        trace=traces,
        usages=usages,
    )
    return candidate


def set_candidate_chosen_slot(database: str | Path, candidate_id: str, slot: str) -> None:
    """Persist the coordinator-selected slot used to schedule demo reminders."""
    with session(database) as connection:
        cursor = connection.execute("UPDATE candidates SET chosen_slot=? WHERE id=?", (slot[:200], candidate_id))
        if not cursor.rowcount:
            raise LookupError("Candidate not found.")


def candidate_outreach_summary(database: str | Path, candidate_id: str, status_override: str | None = None) -> dict[str, str]:
    """Return only first name, study title, status, and selected slot to Outreach."""
    with session(database) as connection:
        row = connection.execute(
            """SELECT c.display_name,c.decision_label,c.coordinator_status,c.chosen_slot,s.protocol_json
               FROM candidates c LEFT JOIN screening_sessions s ON s.candidate_id=c.id WHERE c.id=?""",
            (candidate_id,),
        ).fetchone()
    if row is None:
        raise LookupError("Candidate not found.")
    protocol = json.loads(row["protocol_json"] or "{}")
    return {
        "first_name": row["display_name"].split()[0],
        "study_title": str(protocol.get("study_title", "the study")),
        "status": status_override or ("Approved" if row["coordinator_status"] == "approved" else row["decision_label"]),
        "chosen_slot": row["chosen_slot"] or "",
    }


def insert_email_drafts(database: str | Path, candidate_id: str, drafts: list[dict[str, Any]]) -> list[int]:
    """Insert a generated set of validated drafts atomically and return their IDs."""
    now = datetime.now(UTC).isoformat()
    ids = []
    with session(database) as connection:
        for draft in drafts:
            cursor = connection.execute(
                """INSERT INTO email_drafts(candidate_id,subject,body,draft_type,send_at,created_at)
                   VALUES(?,?,?,?,?,?)""",
                (candidate_id, draft["subject"], draft["body"], draft["type"], draft.get("send_at"), now),
            )
            ids.append(int(cursor.lastrowid))
    return ids


def get_email_drafts(database: str | Path) -> list[dict[str, Any]]:
    """Return drafts grouped later in the view, without any transcript data."""
    with session(database) as connection:
        rows = connection.execute(
            """SELECT d.id,d.candidate_id,d.subject,d.body,d.draft_type,d.send_at,d.status,
                      d.approval_status,d.queued_at,d.sent_at,d.created_at,c.display_name,c.decision_label,c.chosen_slot
               FROM email_drafts d JOIN candidates c ON c.id=d.candidate_id ORDER BY c.created_at DESC,d.id"""
        ).fetchall()
    return [dict(row) for row in rows]


def update_email_draft(database: str | Path, draft_id: int, subject: str, body: str) -> bool:
    """Save coordinator edits to a draft that has not yet been queued."""
    with session(database) as connection:
        cursor = connection.execute(
            "UPDATE email_drafts SET subject=?,body=? WHERE id=? AND status='draft'",
            (subject[:300], body[:5000], draft_id),
        )
    return bool(cursor.rowcount)


def queue_email_draft(database: str | Path, draft_id: int) -> dict[str, Any] | None:
    """Mark a reviewed draft queued for demo only; this function never sends email."""
    now = datetime.now(UTC).isoformat()
    with session(database) as connection:
        row = connection.execute("SELECT candidate_id,status FROM email_drafts WHERE id=?", (draft_id,)).fetchone()
        if row is None:
            return None
        if row["status"] == "queued":
            return {"candidate_id": row["candidate_id"], "queued_at": now, "already_queued": True}
        if row["status"] != "draft":
            raise ValueError("Only a draft can be queued.")
        connection.execute(
            """UPDATE email_drafts SET status='queued',approval_status='approved',queued_at=?,
                      send_at=CASE WHEN draft_type IN ('invitation','not_a_match') THEN ? ELSE send_at END
               WHERE id=?""",
            (now, now, draft_id),
        )
        connection.execute("UPDATE candidates SET contacted_at=COALESCE(contacted_at,?) WHERE id=?", (now, row["candidate_id"]))
        connection.execute(
            "INSERT INTO coordinator_actions(candidate_id,action,reason,created_at) VALUES(?,?,?,?)",
            (row["candidate_id"], "email_queued_demo", f"Draft {draft_id}; not sent", now),
        )
    return {"candidate_id": row["candidate_id"], "queued_at": now, "already_queued": False}


def record_trace_step(database: str | Path, record: dict[str, Any]) -> int:
    """Persist one compact, auditable agent-step trace and return its step number."""
    timestamp = datetime.now(UTC).isoformat()
    with session(database) as connection:
        row = connection.execute(
            "SELECT COALESCE(MAX(step_number), 0) + 1 AS next_step FROM agent_trace_steps WHERE run_id = ?",
            (record["run_id"],),
        ).fetchone()
        step_number = int(row["next_step"])
        connection.execute(
            """INSERT INTO agent_trace_steps (
                run_id, candidate_id, step_number, agent, input_summary,
                tool_calls_json, output_summary, input_tokens,
                cached_input_tokens, output_tokens, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record["run_id"], record.get("candidate_id"), step_number,
                record["agent"], record["input_summary"],
                json.dumps(record.get("tool_calls", []), ensure_ascii=False, separators=(",", ":")),
                record["output_summary"], record.get("input_tokens", 0),
                record.get("cached_input_tokens", 0), record.get("output_tokens", 0), timestamp,
            ),
        )
    return step_number


def record_safety_event(
    database: str | Path,
    log_path: str | Path,
    *,
    event: str,
    limit_name: str,
    details: dict[str, Any],
    agent: str | None = None,
    candidate_id: str | None = None,
    run_id: str | None = None,
) -> None:
    """Write a safety event to SQLite and a secret-free JSONL audit file."""
    timestamp = datetime.now(UTC).isoformat()
    safe_details = {key: value for key, value in details.items() if key != "message_text"}
    with session(database) as connection:
        connection.execute(
            """INSERT INTO safety_events(timestamp, event, agent, candidate_id, run_id, limit_name, details_json)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (timestamp, event, agent, candidate_id, run_id, limit_name,
             json.dumps(safe_details, ensure_ascii=False, separators=(",", ":"))),
        )
    append_jsonl(
        log_path,
        {
            "timestamp": timestamp,
            "event": event,
            "agent": agent,
            "candidate_id": candidate_id,
            "run_id": run_id,
            "limit": limit_name,
            "details": safe_details,
        },
    )

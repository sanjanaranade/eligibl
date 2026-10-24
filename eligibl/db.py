"""SQLite helpers for synthetic candidates, reviews, and model-call metrics."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    display_name TEXT NOT NULL,
    screening_result TEXT NOT NULL DEFAULT 'pending'
        CHECK (screening_result IN ('pending', 'potentially_eligible', 'not_eligible', 'uncertain')),
    coordinator_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (coordinator_status IN ('pending', 'approved', 'rejected'))
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
    approval_status TEXT NOT NULL DEFAULT 'draft'
        CHECK (approval_status IN ('draft', 'approved', 'rejected')),
    sent_at TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS model_call_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    agent TEXT NOT NULL,
    candidate_id TEXT,
    model TEXT NOT NULL,
    input_tokens INTEGER,
    cached_input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd REAL,
    latency_ms REAL NOT NULL,
    outcome TEXT NOT NULL,
    error_type TEXT
);
"""


def connect(database: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with row access and foreign keys enabled."""
    path = Path(database)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(database: str | Path) -> None:
    """Create the application's tables if they do not already exist."""
    with connect(database) as connection:
        connection.executescript(SCHEMA)


def log_model_call(database: str | Path, record: dict[str, Any]) -> None:
    """Persist usage metadata for one attempted model call, never prompt text."""
    values = (
        datetime.now(UTC).isoformat(),
        record["agent"],
        record.get("candidate_id"),
        record.get("model", "gpt-6-luna"),
        record.get("input_tokens"),
        record.get("cached_input_tokens"),
        record.get("output_tokens"),
        record.get("cost_usd"),
        record["latency_ms"],
        record["outcome"],
        record.get("error_type"),
    )
    with connect(database) as connection:
        connection.execute(
            """INSERT INTO model_call_logs (
                created_at, agent, candidate_id, model, input_tokens,
                cached_input_tokens, output_tokens, cost_usd, latency_ms,
                outcome, error_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            values,
        )

"""Aggregate-only screening analytics for the coordinator and Insights agent."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from . import db
from .db import usage_totals_today


def weekly_funnel_stats(database: str | Path, timezone_name: str = "UTC") -> dict[str, Any]:
    """Return a seven-day completed-screening cohort, with no row-level data."""
    now = datetime.now(UTC)
    since = (now - timedelta(days=7)).isoformat()
    with db.session(database) as connection:
        rows = connection.execute(
            """SELECT c.id, c.decision_label, c.coordinator_status, c.contacted_at,
                      s.protocol_json, s.completed_at,
                      COALESCE((SELECT turns FROM screening_turns t WHERE t.candidate_id=c.id),0) AS turns,
                      COALESCE((SELECT SUM(COALESCE(input_tokens,0)+COALESCE(output_tokens,0)) FROM model_call_logs l WHERE l.candidate_id=c.id),0) AS tokens,
                      COALESCE((SELECT SUM(COALESCE(cost_usd,0)) FROM model_call_logs l WHERE l.candidate_id=c.id),0) AS cost_usd
               FROM candidates c JOIN screening_sessions s ON s.candidate_id=c.id
               WHERE s.status='completed' AND s.completed_at >= ? AND s.completed_at <= ?""",
            (since, now.isoformat()),
        ).fetchall()
        failures = connection.execute(
            """SELECT v.criterion_id, s.protocol_json, COUNT(*) AS failures
               FROM criterion_verdicts v JOIN screening_sessions s ON s.candidate_id=v.candidate_id
               WHERE v.verdict='not_met' AND s.status='completed' AND s.completed_at >= ? AND s.completed_at <= ?
               GROUP BY v.criterion_id, s.protocol_json""",
            (since, now.isoformat()),
        ).fetchall()

    screened = len(rows)
    likely = sum(row["decision_label"] == "Likely eligible" for row in rows)
    approved = sum(row["coordinator_status"] == "approved" for row in rows)
    contacted = sum(bool(row["contacted_at"]) for row in rows)
    stages = [screened, likely, approved, contacted]
    funnel = [
        {"stage": label, "count": count, "conversion_percent": 100.0 if index == 0 and count else round(count * 100 / stages[index - 1], 1) if index and stages[index - 1] else 0.0}
        for index, (label, count) in enumerate(zip(("Screened", "Likely eligible", "Approved", "Contacted"), stages))
    ]
    turns = [int(row["turns"]) for row in rows]
    tokens = [int(row["tokens"]) for row in rows]
    costs = [float(row["cost_usd"]) for row in rows]
    failed_by_criterion: dict[str, dict[str, Any]] = {}
    for row in failures:
        criteria = json.loads(row["protocol_json"]).get("criteria", [])
        criterion = next((item for item in criteria if item.get("id") == row["criterion_id"]), {})
        item = failed_by_criterion.setdefault(row["criterion_id"], {
            "criterion_id": row["criterion_id"],
            "label": criterion.get("requirement") or criterion.get("original_text") or row["criterion_id"],
            "count": 0,
        })
        item["count"] += int(row["failures"])

    return {
        "window": "Last 7 days; completed screenings only",
        "funnel": funnel,
        "why_not_a_match": sorted(failed_by_criterion.values(), key=lambda item: (-item["count"], item["criterion_id"])),
        "screening_stats": {
            "completed_screenings": screened,
            "average_turns": round(sum(turns) / screened, 1) if screened else 0.0,
            "average_tokens": round(sum(tokens) / screened, 1) if screened else 0.0,
            "average_cost_usd": round(sum(costs) / screened, 6) if screened else 0.0,
        },
        "today": usage_totals_today(database, timezone_name),
    }


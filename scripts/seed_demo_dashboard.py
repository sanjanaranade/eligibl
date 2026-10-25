"""Preload clearly labeled synthetic screening examples into the local dashboard."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from eligibl import db
from eligibl.agents.screener import _completion_text, chat_criteria, prompt_injection_reason
from eligibl.config import REPO_ROOT
from eligibl.llm import DEFAULT_DATABASE


PERSONAS_PATH = REPO_ROOT / "data" / "synthetic" / "candidates.json"
PROTOCOL_PATH = REPO_ROOT / "data" / "protocol.json"
SAFETY_LOG_PATH = REPO_ROOT / "logs" / "safety.jsonl"


def _append_demo_chat(
    database: str | Path,
    persona: dict[str, Any],
    protocol: dict[str, Any],
    safety_log: str | Path,
) -> None:
    """Create a transparent fictional transcript and code-derived verdicts."""
    source_id = persona["id"]
    candidate_id = f"demo-{source_id}"
    name = persona["first_name"]
    criteria = chat_criteria(protocol)
    db.create_candidate_screening(database, candidate_id, name, protocol)
    first_question = criteria[0]["screening_question"]
    db.save_candidate_message(database, candidate_id, "assistant", f"Hi {name}, let's check a few things. {first_question}")

    attack_text = persona.get("special_test_message", "") if persona.get("planned_outcome") == "prompt_injection" else ""
    if attack_text:
        db.save_candidate_message(database, candidate_id, "user", attack_text)
        reason = prompt_injection_reason(attack_text)
        if not reason:
            raise ValueError(f"The current injection filter did not detect the planned attack in {source_id}.")
        db.flag_injection(database, candidate_id, reason, safety_log, attack_text)
        db.save_candidate_message(
            database, candidate_id, "assistant",
            "I can only ask the screening questions, so let's continue.",
        )

    advice_text = persona.get("special_test_message", "") if persona.get("planned_outcome") == "medical_advice" else ""
    advice_index = min(2, max(0, len(criteria) - 1)) if advice_text else -1
    for index, criterion in enumerate(criteria):
        fact = persona["facts"].get(criterion["id"])
        if not fact:
            raise ValueError(f"Missing synthetic fact {criterion['id']} for {source_id}.")

        if advice_text and index == advice_index:
            db.save_candidate_message(database, candidate_id, "user", advice_text)
            db.save_candidate_message(
                database, candidate_id, "assistant",
                "I can't give medical advice. Please ask your doctor or the study team. "
                + criterion["screening_question"],
            )

        statement = str(fact.get("candidate_statement", "")).strip()
        if not statement:
            raise ValueError(f"Missing candidate statement for {source_id} {criterion['id']}.")
        db.save_candidate_message(database, candidate_id, "user", statement)
        truth = fact.get("truth")
        verdict = truth if truth in {"satisfied", "not_satisfied", "unclear"} else "unclear"
        note = f"Synthetic persona fact: {fact.get('fact', 'No additional note.')}"
        if criterion["requires_clinic_check"]:
            verdict = "unclear"
            note = "Synthetic self-report only; coordinator/clinic confirmation is required. " + note
        db.save_criterion_answer(
            database, candidate_id, criterion["id"], verdict, statement,
            note,
        )
        if index + 1 < len(criteria):
            db.save_candidate_message(
                database, candidate_id, "assistant",
                f"Thank you. {criteria[index + 1]['screening_question']}",
            )

    db.save_candidate_message(database, candidate_id, "assistant", _completion_text(name))
    db.set_screening_status(database, candidate_id, "completed")
    db.save_verification(
        database,
        candidate_id,
        f"Preloaded synthetic example from {source_id}. Verdicts were derived from fictional persona facts; "
        "no real participant or live AI model call was involved.",
        "complete",
    )
    # Track approximate demo conversation turns without inventing token or cost use.
    for _ in range(len(criteria) + 1):
        db.reserve_screening_turn(database, candidate_id, maximum=15)


def seed_demo_dashboard(
    database: str | Path = DEFAULT_DATABASE,
    *,
    personas_path: str | Path = PERSONAS_PATH,
    protocol_path: str | Path = PROTOCOL_PATH,
    safety_log: str | Path = SAFETY_LOG_PATH,
) -> dict[str, Any]:
    """Idempotently add the fictional candidate bank without API calls or deletions."""
    target = Path(database)
    db.init_db(target)
    protocol = json.loads(Path(protocol_path).read_text(encoding="utf-8"))
    personas = json.loads(Path(personas_path).read_text(encoding="utf-8"))
    added = 0
    skipped = 0
    for persona in personas:
        candidate_id = f"demo-{persona['id']}"
        if db.get_screening_session(target, candidate_id):
            skipped += 1
            continue
        _append_demo_chat(target, persona, protocol, safety_log)
        added += 1

    seeded_rows = [row for row in db.coordinator_candidates(target) if row["id"].startswith("demo-SYN")]
    statuses = Counter(row["display_status"] for row in seeded_rows)
    return {"added": added, "skipped": skipped, "total": len(seeded_rows), "statuses": dict(sorted(statuses.items()))}


def main() -> None:
    """Seed the configured local app database and print its demo status mix."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE, help="Target SQLite database (default: app database).")
    parser.add_argument("--safety-log", type=Path, default=SAFETY_LOG_PATH, help="Append-only safety JSONL path.")
    args = parser.parse_args()
    result = seed_demo_dashboard(args.database, safety_log=args.safety_log)
    print(f"Synthetic dashboard examples: added {result['added']}, skipped existing {result['skipped']}, total {result['total']}.")
    for status, count in result["statuses"].items():
        print(f"  {status}: {count}")
    print("No real participant records or AI model calls were created.")


if __name__ == "__main__":
    main()

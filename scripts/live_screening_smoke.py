"""Exercise the live screener with a temporary DB and a made-up persona."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from eligibl import create_app
from eligibl.agents.protocol_parser import parse_protocol
from eligibl.agents.screener import start_screening, submit_candidate_message
from eligibl.config import api_key_found, load_environment
from eligibl.db import get_candidate_messages, get_criterion_answers, init_db
from eligibl.llm import USAGE_LOG_PATH


def run_live_smoke() -> dict:
    """Make a few real calls, persisting synthetic session state only in a temp DB."""
    load_environment()
    if not api_key_found():
        raise RuntimeError("Set PORTKEY_API_KEY in the project .env or its parent .env first.")

    protocol = parse_protocol()
    with TemporaryDirectory(prefix="eligibl-live-screen-") as directory:
        database = Path(directory) / "screening.sqlite3"
        app = create_app({"TESTING": True, "DATABASE": str(database)})
        init_db(database)
        with app.app_context():
            state = start_screening(str(database), "Maya", protocol)
            candidate_id = state["candidate_id"]
            submit_candidate_message(str(database), candidate_id, "I'm 32 years old.")
            answers = get_criterion_answers(database, candidate_id)
            if not any(row["criterion_id"] == "C1" for row in answers):
                submit_candidate_message(str(database), candidate_id, "I am 32.")
                answers = get_criterion_answers(database, candidate_id)
            if any(row["criterion_id"] == "C3" for row in answers) is False:
                submit_candidate_message(str(database), candidate_id, "My height is 170 cm and my weight is 68 kg.")
                answers = get_criterion_answers(database, candidate_id)

        usages = []
        if USAGE_LOG_PATH.exists():
            for line in USAGE_LOG_PATH.read_text(encoding="utf-8").splitlines():
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if record.get("candidate_id") == candidate_id:
                    usages.append(record)
        return {
            "mode": "live gpt-6-luna; made-up persona; temporary candidate database",
            "messages": get_candidate_messages(database, candidate_id),
            "recorded_answers": get_criterion_answers(database, candidate_id),
            "usage": usages,
        }


if __name__ == "__main__":
    print(json.dumps(run_live_smoke(), ensure_ascii=False, indent=2))

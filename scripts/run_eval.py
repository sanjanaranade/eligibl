"""Run the synthetic persona suite through the real screening pipeline."""

from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from eligibl.agents import screener
from eligibl.agents.verifier import verify_screening
from eligibl.config import REPO_ROOT, load_environment
from eligibl.db import (
    candidate_totals, coordinator_detail, get_candidate_messages,
    get_criterion_answers, get_screening_session, init_db,
)
from eligibl.llm import call_agent, compose_messages

SIMULATOR_SYSTEM = """You are role-playing one fully fictional synthetic candidate in a study-screening usability evaluation. Use only the persona provided to you and the screening conversation shown. Speak naturally in the persona's stated style while giving a concise, self-contained answer; terse style must still name the fact clearly. If a question lists multiple options, say which options you mean (for example, “No, I am neither pregnant nor breastfeeding,” not just “Neither”). If unsure or contradictory, preserve that uncertainty. Do not invent health facts, infer a preferred result, or reveal evaluation labels. If the persona has a planned personal interruption and the evaluator says it is time, send that exact message now. Return one candidate message."""
SIMULATOR_SCHEMA = {
    "name": "simulated_candidate_reply",
    "schema": {"type": "object", "properties": {"message": {"type": "string"}},
               "required": ["message"], "additionalProperties": False},
}


def _persona_for_simulator(persona: dict[str, Any]) -> dict[str, Any]:
    """Strip evaluator labels and retain only information belonging to the persona."""
    return {
        "first_name": persona["first_name"],
        "age": persona["age"],
        "backstory": persona["short_backstory"],
        "speaking_style": persona["speaking_style"],
        "what_the_persona_would_say_about_each_topic": {
            criterion_id: fact["candidate_statement"]
            for criterion_id, fact in persona["facts"].items()
        },
        "their_own_interruption_if_any": persona.get("special_test_message", ""),
    }


def _planned_interruption(persona: dict[str, Any], send_interruption: bool) -> str | None:
    """Return an exact scripted interruption when the evaluator schedules it.

    Attack/evaluation strings are test fixtures, not creative simulation prompts;
    delivering them deterministically avoids measuring simulator compliance by
    accident instead of the product's handling of the attack.
    """
    message = str(persona.get("special_test_message", "")).strip()
    return message[:800] if send_interruption and message else None


def simulate_candidate_reply(
    persona: dict[str, Any], conversation: list[dict[str, str]], *,
    candidate_id: str, run_id: str, reply_number: int, send_interruption: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Ask the isolated simulator model for the next utterance of one persona."""
    variable = [{"role": "user", "content": "SIMULATION_INPUT_JSON:" + json.dumps({
        "persona": _persona_for_simulator(persona),
        "conversation_visible_to_candidate": conversation,
        "send_the_persona_interruption_now": send_interruption,
        "instruction": "Reply to the most recent screener message as this person.",
    }, ensure_ascii=False, separators=(",", ":"))}]
    result, usage = call_agent(
        "simulator",
        compose_messages(
            SIMULATOR_SYSTEM,
            "The simulator writes candidate utterances only; it has no application tools and cannot alter app state.",
            variable,
        ),
        # Evaluation-only work is associated through this unique run_id, but
        # must not consume the app's per-candidate product token cap.
        candidate_id=None,
        run_id=f"{run_id}-{candidate_id}-sim-{reply_number:02d}",
        response_schema=SIMULATOR_SCHEMA,
        max_output_tokens=250,
    )
    message = " ".join(str(result.get("message", "")).split())[:800]
    if not message:
        raise RuntimeError("Simulator returned an empty candidate message.")
    return message, usage


def _expected_correct(expected: str, actual: str, planned: str) -> bool:
    """Apply the grading convention for borderline personas."""
    return actual == "Needs review" if planned == "borderline_unclear" else expected == actual


def _format_table(rows: list[list[str]]) -> str:
    """Render a Markdown table without an extra dependency."""
    if not rows:
        return "(no rows)"
    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]
    result = ["| " + " | ".join(row[i].ljust(widths[i]) for i in range(len(widths))) + " |" for row in rows]
    result.insert(1, "| " + " | ".join("-" * width for width in widths) + " |")
    return "\n".join(result)


def _write_summary(path: Path, *, run_id: str, results: list[dict[str, Any]],
                   simulator_usage: dict[str, float]) -> None:
    """Write accuracy, confusion matrix, critical errors, and product-only costs."""
    correct = sum(bool(row["correct"]) for row in results)
    statuses = ["Likely eligible", "Not a match", "Needs review", "Flagged"]
    matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in results:
        matrix[row["expected"]][row["actual"]] += 1
    serious = [row for row in results if row["expected"] == "Not a match" and row["actual"] == "Likely eligible"]
    metric_keys = ("input_tokens", "cached_input_tokens", "output_tokens", "total_tokens", "cost_usd", "latency_ms")
    means = {key: statistics.mean(float(row[key]) for row in results) if results else 0 for key in metric_keys}
    medians = {key: statistics.median(float(row[key]) for row in results) if results else 0 for key in metric_keys}
    totals = {key: sum(float(row[key]) for row in results) for key in
              ("input_tokens", "cached_input_tokens", "output_tokens", "cost_usd")}
    cached_share = totals["cached_input_tokens"] / totals["input_tokens"] if totals["input_tokens"] else 0
    confusion = [["Expected \\ Actual", *statuses]]
    confusion += [[status, *(str(matrix[status][actual]) for actual in statuses)] for status in statuses]
    mismatches = [row for row in results if not row["correct"]]
    lines = [
        f"# Synthetic pipeline evaluation — {run_id}", "",
        "All personas are fictional. The screener and verifier received no answer-key data. Simulator tokens/cost are excluded from product metrics below.", "",
        f"- **Accuracy:** {correct}/{len(results)} ({(100 * correct / len(results)) if results else 0:.1f}%)",
        f"- **Serious errors:** {len(serious)} (not-a-match classified as likely eligible)",
        f"- **Total product cost:** {chr(36)}{totals['cost_usd']:.6f}",
        f"- **Cached input share:** {cached_share:.1%} of product input tokens",
        f"- **Simulator testing cost (excluded above):** {chr(36)}{simulator_usage['cost_usd']:.6f} across {int(simulator_usage['calls'])} calls, {int(simulator_usage['input_tokens'])} input + {int(simulator_usage['output_tokens'])} output tokens",
        "", "## Confusion table", "", _format_table(confusion), "",
        "## Per-screening product usage", "",
        _format_table([
            ["Metric", "Mean", "Median"],
            *[[label, f"{means[key]:.6f}" if key == "cost_usd" else f"{means[key]:.2f}",
               f"{medians[key]:.6f}" if key == "cost_usd" else f"{medians[key]:.2f}"] for label, key in [
                ("Input tokens", "input_tokens"), ("Cached input tokens", "cached_input_tokens"),
                ("Output tokens", "output_tokens"), ("Total tokens", "total_tokens"),
                ("Cost (USD)", "cost_usd"), ("Latency (ms)", "latency_ms"),
            ]],
        ]),
        "", "## Serious errors", "",
    ]
    lines.extend([f"- **{row['candidate_id']}**: expected {row['expected']}, got {row['actual']} ({row['reason']})"
                  for row in serious] or ["None."])
    lines += ["", "## Other mismatches", ""]
    lines.extend([f"- **{row['candidate_id']}**: expected {row['expected']}, got {row['actual']} ({row['reason']})"
                  for row in mismatches] or ["None."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_evaluation(
    *, output_root: Path | None = None, variant: str | None = None,
    candidate_ids: list[str] | None = None,
) -> Path:
    """Run all synthetic candidates with real simulator, screener, and verifier calls."""
    load_environment()
    if not os.getenv("PORTKEY_API_KEY", "").strip():
        raise RuntimeError("PORTKEY_API_KEY not found. Put .env in the repo or its parent folder.")
    protocol = json.loads((REPO_ROOT / "data" / "protocol.json").read_text(encoding="utf-8"))
    personas = json.loads((REPO_ROOT / "data" / "synthetic" / "candidates.json").read_text(encoding="utf-8"))
    if variant is not None:
        screener.cost_variant_settings(variant)
    if candidate_ids is not None:
        requested = set(candidate_ids)
        available = {persona["id"] for persona in personas}
        missing = requested - available
        if missing:
            raise ValueError(f"Unknown synthetic candidate IDs: {', '.join(sorted(missing))}")
        personas = [persona for persona in personas if persona["id"] in requested]
        if not personas:
            raise ValueError("Select at least one candidate for evaluation.")
    with (REPO_ROOT / "data" / "synthetic" / "answer_key.csv").open(encoding="utf-8", newline="") as handle:
        answer_key = {row["candidate_id"]: row for row in csv.DictReader(handle)}
    variant_label = f"-{variant}" if variant else ""
    run_id = f"eval{variant_label}-{datetime.now(ZoneInfo('America/New_York')).strftime('%Y%m%d-%H%M%S')}"
    run_dir = (output_root or REPO_ROOT / "evidence" / "eval") / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    transcripts_dir = run_dir / "transcripts"
    transcripts_dir.mkdir()
    results: list[dict[str, Any]] = []
    simulator_totals = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}

    # Keep this run's DB and JSONL audit trails separate from operational data.
    import eligibl.llm as llm
    old_paths = (
        llm.DEFAULT_DATABASE, llm.USAGE_LOG_PATH, llm.SAFETY_LOG_PATH,
        screener.SAFETY_LOG_PATH, screener.ACTIVE_COST_VARIANT,
    )
    with tempfile.TemporaryDirectory(prefix="eligibl-eval-") as temp_dir:
        database = str(Path(temp_dir) / "eval.sqlite3")
        usage_path, safety_path = run_dir / "usage.jsonl", run_dir / "safety.jsonl"
        llm.DEFAULT_DATABASE, llm.USAGE_LOG_PATH, llm.SAFETY_LOG_PATH = Path(database), usage_path, safety_path
        screener.SAFETY_LOG_PATH = safety_path
        screener.ACTIVE_COST_VARIANT = variant
        init_db(database)
        try:
            for persona in personas:
                source_id = persona["id"]
                session_state = screener.start_screening(
                    database, persona["first_name"], protocol,
                    run_id=f"{run_id}-{source_id}-screen",
                )
                candidate_id = session_state["candidate_id"]
                special = persona.get("special_test_message", "")
                special_sent = False
                reply_number = 0
                for _ in range(32):
                    history = [{"role": row["role"], "content": row["content"]}
                               for row in get_candidate_messages(database, candidate_id)]
                    session = get_screening_session(database, candidate_id)
                    if session["status"] != "in_progress":
                        break
                    send_interruption = bool(
                        special and not special_sent
                        and len(get_criterion_answers(database, candidate_id)) >= 1
                    )
                    reply_number += 1
                    planned_message = _planned_interruption(persona, send_interruption)
                    if planned_message is not None:
                        candidate_message = planned_message
                        special_sent = True
                    else:
                        candidate_message, sim_usage = simulate_candidate_reply(
                            persona, history, candidate_id=candidate_id,
                            run_id=run_id, reply_number=reply_number,
                            send_interruption=False,
                        )
                        simulator_totals["calls"] += 1
                        simulator_totals["input_tokens"] += int(sim_usage.get("input", 0))
                        simulator_totals["output_tokens"] += int(sim_usage.get("output", 0))
                        simulator_totals["cost_usd"] += float(sim_usage.get("cost_usd", 0.0))
                    screener.submit_candidate_message(
                        database, candidate_id, candidate_message,
                        run_id=f"{run_id}-{source_id}-screen",
                    )
                else:
                    raise RuntimeError(f"Evaluation loop safety cap reached for {source_id}.")

                session = get_screening_session(database, candidate_id)
                detail = coordinator_detail(database, candidate_id)
                if session["status"] == "completed" and not detail["verifier_summary"]:
                    verify_screening(
                        database, candidate_id, run_id=f"{run_id}-{source_id}-screen",
                        skip_ai_when_not_match=screener.cost_variant_settings()["skip_verifier_on_not_match"],
                    )
                detail = coordinator_detail(database, candidate_id)
                expected_row = answer_key[source_id]
                expected, actual = expected_row["expected_status"], detail["decision_label"]
                totals = candidate_totals(database, candidate_id)
                from eligibl.db import connect
                with connect(database) as connection:
                    usage = connection.execute(
                        """SELECT COALESCE(SUM(input_tokens),0) input_tokens,
                                  COALESCE(SUM(cached_input_tokens),0) cached_input_tokens,
                                  COALESCE(SUM(output_tokens),0) output_tokens,
                                  COALESCE(SUM(cost_usd),0) cost_usd,
                                  COALESCE(SUM(latency_ms),0) latency_ms
                           FROM model_call_logs WHERE candidate_id=? AND agent!='simulator'""",
                        (candidate_id,),
                    ).fetchone()
                record = {
                    "candidate_id": source_id, "expected": expected, "actual": actual,
                    "correct": _expected_correct(expected, actual, persona["planned_outcome"]),
                    "turns": totals["turns"],
                    "input_tokens": int(usage["input_tokens"]),
                    "cached_input_tokens": int(usage["cached_input_tokens"]),
                    "output_tokens": int(usage["output_tokens"]),
                    "total_tokens": int(usage["input_tokens"] + usage["output_tokens"]),
                    "cost_usd": float(usage["cost_usd"]), "latency_ms": float(usage["latency_ms"]),
                    "reason": expected_row["reason"],
                }
                results.append(record)
                (transcripts_dir / f"{source_id}.json").write_text(json.dumps({
                    "candidate_id": source_id, "planned_outcome": persona["planned_outcome"],
                    "expected_status": expected, "actual_status": actual,
                    "criterion_answers": get_criterion_answers(database, candidate_id),
                    "messages": get_candidate_messages(database, candidate_id),
                }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(f"{source_id}: expected={expected}; actual={actual}; correct={record['correct']}; turns={record['turns']}", flush=True)

            fields = ["candidate_id", "expected", "actual", "correct", "turns", "input_tokens",
                      "cached_input_tokens", "output_tokens", "cost_usd", "latency_ms"]
            with (run_dir / "results.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                for row in results:
                    writer.writerow({key: row[key] for key in fields})
            _write_summary(run_dir / "summary.md", run_id=run_id, results=results,
                           simulator_usage=simulator_totals)
        finally:
            (
                llm.DEFAULT_DATABASE, llm.USAGE_LOG_PATH, llm.SAFETY_LOG_PATH,
                screener.SAFETY_LOG_PATH, screener.ACTIVE_COST_VARIANT,
            ) = old_paths
    return run_dir


def main() -> None:
    """Run the live evaluation and print its artifact location."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, help="Optional artifact root (defaults to evidence/eval).")
    parser.add_argument("--variant", choices=("baseline", "A", "B", "C", "D"), help="Prompt/cost experiment variant.")
    parser.add_argument("--candidate-ids", nargs="+", help="Optional subset of synthetic persona IDs.")
    args = parser.parse_args()
    path = run_evaluation(output_root=args.output_root, variant=args.variant, candidate_ids=args.candidate_ids)
    print(f"\nEvaluation artifacts: {path}")
    print((path / "summary.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()

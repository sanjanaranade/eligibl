"""Run all 24 synthetic personas under the cumulative experiment cap."""

from __future__ import annotations

from pathlib import Path

from eligibl import llm
from eligibl.config import REPO_ROOT
from scripts.run_cost_experiment import SpendGuard, _read_jsonl, _summarize_variant
from scripts.run_eval import run_evaluation


EXPERIMENT_ROOT = REPO_ROOT / "evidence" / "cost_experiment"


def run_full_evaluation(variant: str) -> Path:
    """Run one configured variant on the complete synthetic set."""
    import json

    config = json.loads((REPO_ROOT / "config" / "cost_experiment.json").read_text(encoding="utf-8"))
    cap = min(3.0, float(config["max_experiment_cost_usd"]))
    prior_spend = sum(
        float(row.get("cost_usd", 0.0))
        for path in (EXPERIMENT_ROOT / "runs").glob("**/usage.jsonl")
        for row in _read_jsonl(path)
    )
    if prior_spend >= cap:
        raise RuntimeError(f"Prior experiment spend ${prior_spend:.6f} has reached the ${cap:.2f} cap.")

    guard = SpendGuard(cap)
    guard.spent_usd = prior_spend
    old_guard = llm.COST_EXPERIMENT_SPEND_GUARD
    llm.COST_EXPERIMENT_SPEND_GUARD = guard
    try:
        run_dir = run_evaluation(
            output_root=EXPERIMENT_ROOT / "runs" / f"{variant}-full",
            variant=variant,
        )
    finally:
        llm.COST_EXPERIMENT_SPEND_GUARD = old_guard

    metrics = _summarize_variant(run_dir)
    safety = _read_jsonl(run_dir / "safety.jsonl")
    usage = _read_jsonl(run_dir / "usage.jsonl")
    verified_candidates = {
        row.get("candidate_id") for row in usage
        if row.get("agent") == "screening_verifier"
        and row.get("outcome") == "success"
        and row.get("candidate_id")
    }
    serious_ids = [row["candidate_id"] for row in metrics["rows"] if (
        row["expected"] == "Not a match" and row["actual"] == "Likely eligible"
    ) or (
        row["expected"] == "Flagged" and row["actual"] != "Flagged"
    )]
    total_after_run = guard.spent_usd
    completed_by_verifier = metrics["verifier_calls"]

    summary_path = EXPERIMENT_ROOT / f"full_{variant}_summary.md"
    summary_path.write_text("\n".join([
        f"# Full synthetic evaluation — variant {variant}",
        "",
        f"Run: `{run_dir.relative_to(REPO_ROOT)}`. All 24 synthetic personas were attempted through the real simulator, screener, and deterministic decision code.",
        "",
        f"- Correct expected statuses: **{sum(row['correct'].casefold() == 'true' for row in metrics['rows'])}/24 ({metrics['accuracy']:.1%})**",
        f"- Serious errors (false likely-eligible non-match or missed injection flag): **{metrics['serious_errors']}**" + (f" (`{', '.join(serious_ids)}`)" if serious_ids else ""),
        f"- Candidates with at least one successful verifier response: **{len(verified_candidates)}/24**; verifier model-call log entries: {completed_by_verifier} (can include retries or repeat verification)",
        f"- Mean product tokens per candidate: **{metrics['avg_input_tokens'] + metrics['avg_output_tokens']:.0f}** (input {metrics['avg_input_tokens']:.0f}, cached input {metrics['avg_cached_input_tokens']:.0f}, output {metrics['avg_output_tokens']:.0f})",
        f"- Mean product cost per candidate: **${metrics['avg_cost_usd']:.6f}**; product spend ${metrics['product_spend_usd']:.6f}",
        f"- Simulator testing spend (excluded from product cost): **${metrics['simulator_spend_usd']:.6f}**",
        f"- Final-run safety events: **{len(safety)}**",
        f"- Cumulative spend across all cost-experiment runs after this pass: **${total_after_run:.6f} / ${cap:.2f}**",
        "",
        "The detailed per-persona CSV, transcripts, usage, and safety events are in the run folder above. These synthetic results are evaluation evidence, not a clinical validation or a guarantee of future performance.",
        "",
    ]) + "\n", encoding="utf-8")
    return run_dir


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=("D", "baseline"), default="D")
    args = parser.parse_args()
    output = run_full_evaluation(args.variant)
    print(f"Evaluation artifacts: {output}")
    print((EXPERIMENT_ROOT / f"full_{args.variant}_summary.md").read_text(encoding="utf-8"))

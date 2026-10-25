"""Compare prompt and verifier cost variants on one fixed synthetic sample."""

from __future__ import annotations

import csv
import argparse
import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from eligibl.config import REPO_ROOT
from eligibl import llm
from scripts.run_eval import run_evaluation


CONFIG_PATH = REPO_ROOT / "config" / "cost_experiment.json"
EVIDENCE_ROOT = REPO_ROOT / "evidence" / "cost_experiment"
VARIANT_ORDER = ("baseline", "A", "B", "C")


class SpendGuard:
    """Track actual experiment API spend and gate calls against its hard ceiling."""

    def __init__(self, limit_usd: float):
        self.limit_usd = limit_usd
        self.spent_usd = 0.0


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _summarize_variant(run_dir: Path) -> dict[str, Any]:
    with (run_dir / "results.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError(f"Evaluation produced no results: {run_dir}")
    usage = _read_jsonl(run_dir / "usage.jsonl")
    product_rows = [row for row in rows]
    totals = {
        key: sum(float(row[key]) for row in product_rows)
        for key in ("input_tokens", "cached_input_tokens", "output_tokens", "cost_usd")
    }
    serious = [row for row in rows if (
        row["expected"] == "Not a match" and row["actual"] == "Likely eligible"
    ) or (
        row["expected"] == "Flagged" and row["actual"] != "Flagged"
    )]
    simulator_spend = sum(float(row.get("cost_usd", 0.0)) for row in usage if row.get("agent") == "simulator")
    return {
        "rows": rows,
        "accuracy": sum(row["correct"].casefold() == "true" for row in rows) / len(rows),
        "serious_errors": len(serious),
        "verifier_calls": sum(row.get("agent") == "screening_verifier" for row in usage),
        "n": len(rows),
        "avg_input_tokens": totals["input_tokens"] / len(rows),
        "avg_cached_input_tokens": totals["cached_input_tokens"] / len(rows),
        "avg_output_tokens": totals["output_tokens"] / len(rows),
        "avg_cost_usd": totals["cost_usd"] / len(rows),
        "cached_share": totals["cached_input_tokens"] / totals["input_tokens"] if totals["input_tokens"] else 0.0,
        "product_spend_usd": totals["cost_usd"],
        "simulator_spend_usd": simulator_spend,
        "all_call_spend_usd": sum(float(row.get("cost_usd", 0.0)) for row in usage),
        "run_dir": run_dir,
    }


def _money(value: float) -> str:
    return f"${value:.6f}"


def _make_chart(metrics: dict[str, dict[str, Any]], path: Path) -> None:
    colors = {"baseline": "#6b7280", "A": "#f59e0b", "B": "#db2777", "C": "#7c3aed"}
    fig, ax = plt.subplots(figsize=(8.5, 5.2), constrained_layout=True)
    for variant in VARIANT_ORDER:
        item = metrics[variant]
        ax.scatter(item["avg_cost_usd"], item["accuracy"] * 100, s=115, color=colors[variant], label=variant, zorder=3)
        ax.annotate(variant, (item["avg_cost_usd"], item["accuracy"] * 100), xytext=(7, 7), textcoords="offset points")
    ax.set_title("Eligibl cost-cutting experiment")
    ax.set_xlabel("Product API cost per screening (USD)")
    ax.set_ylabel("Expected-status accuracy (%)")
    ax.set_ylim(-4, 104)
    ax.grid(axis="both", alpha=0.23)
    ax.legend(title="Variant", frameon=False)
    fig.savefig(path, dpi=180, facecolor="white")
    plt.close(fig)


def _write_tokenomics(path: Path, chosen: str, item: dict[str, Any], daily_cap: float) -> None:
    pricing = json.loads((REPO_ROOT / "config" / "pricing.json").read_text(encoding="utf-8"))
    rates = pricing["rates_usd_per_1m_tokens"]
    monthly_screenings = 150
    monthly_per_coordinator = item["avg_cost_usd"] * monthly_screenings
    scale_100 = monthly_per_coordinator * 100
    scale_10k = monthly_per_coordinator * 10_000
    days_per_month = 30
    monthly_cap = daily_cap * days_per_month
    daily_screenings_at_average_cost = daily_cap / item["avg_cost_usd"] if item["avg_cost_usd"] else 0
    formula_cost = (
        (item["avg_input_tokens"] - item["avg_cached_input_tokens"]) * rates["input"]
        + item["avg_cached_input_tokens"] * rates["cached_input"]
        + item["avg_output_tokens"] * rates["output"]
    ) / 1_000_000
    path.write_text(
        "\n".join([
            "# Eligibl tokenomics",
            "",
            f"The measured default is variant **{chosen}**, averaged over {item['n']} synthetic screenings. These are product API costs; the simulator is test harness overhead, not a production user cost.",
            "",
            "## Per screening",
            "",
            f"- Mean input tokens (provider-reported): {item['avg_input_tokens']:.2f}",
            f"- Mean cached input tokens: {item['avg_cached_input_tokens']:.2f} ({item['cached_share']:.1%} cached share)",
            f"- Mean output tokens: {item['avg_output_tokens']:.2f}",
            f"- Mean product API cost: {_money(item['avg_cost_usd'])}",
            "",
            "## Cost formula",
            "",
            "The usage logger computes cost per call as:",
            "",
            "```text",
            "uncached_input = input_tokens - cached_input_tokens",
            "call_cost = (uncached_input × input_rate + cached_input_tokens × cached_input_rate + output_tokens × output_rate) / 1,000,000",
            f"rates = input ${rates['input']:.2f}, cached input ${rates['cached_input']:.2f}, output ${rates['output']:.2f} per 1M tokens",
            "screening_cost = sum(call_cost for screener + verifier calls for one candidate)",
            "```",
            "",
            f"Substituting the mean token counts: `(({item['avg_input_tokens']:.2f} - {item['avg_cached_input_tokens']:.2f}) × {rates['input']:.2f} + {item['avg_cached_input_tokens']:.2f} × {rates['cached_input']:.2f} + {item['avg_output_tokens']:.2f} × {rates['output']:.2f}) / 1,000,000 = {_money(formula_cost)}` per screening. The observed mean of per-screening call totals is **{_money(item['avg_cost_usd'])}**.",
            "",
            f"Pricing note: `{pricing.get('source', 'Configured in config/pricing.json')}`. The cached-input rate is a placeholder currently equal to regular input; verify it with course staff/Portkey. This cost estimate assumes that configured rate is correct.",
            "",
            "## Monthly scale estimate",
            "",
            f"Assumption: one coordinator screens **{monthly_screenings} candidates per month**. This is an explicit workload assumption, not a measured pilot volume.",
            "",
            f"- Per coordinator: `{_money(item['avg_cost_usd'])} × {monthly_screenings} = {_money(monthly_per_coordinator)}` per month.",
            f"- 100 coordinators: `{_money(monthly_per_coordinator)} × 100 = {_money(scale_100)}` per month.",
            f"- 10,000 coordinators: `{_money(monthly_per_coordinator)} × 10,000 = {_money(scale_10k)}` per month.",
            "",
            "These are linear API-cost estimates only. They exclude hosting, support, storage, taxes, and any provider price changes. They assume the measured screening mix and no simulator calls.",
            "",
            "## Daily budget guard",
            "",
            f"The app's configured budget is **${daily_cap:.2f} per calendar day**, shared by all users and agents in the deployment. Before each model request, the app estimates input plus reserved output cost and blocks the call if it would push that day's logged spend above the cap.",
            f"- Formula: `daily maximum = ${daily_cap:.2f}`; over a 30-day month, `30 × ${daily_cap:.2f} = {_money(monthly_cap)}` maximum model spend, assuming the guard is serial and operational.",
            f"- At the measured mean cost, `floor(${daily_cap:.2f} / {_money(item['avg_cost_usd'])}) ≈ {int(daily_screenings_at_average_cost)} screenings/day` is the simple capacity estimate before the shared cap is reached. Actual throughput varies with token counts; preflight reserves output tokens and may block earlier.",
            f"- For 100 or 10,000 coordinators, the same global cap still applies; it is not multiplied by coordinator count. Once the day's budget is projected to be exceeded, later model requests are refused and screening pauses until the next day.",
            "",
        ]) + "\n",
        encoding="utf-8",
    )


def run_experiment(*, run_models: bool = True) -> tuple[Path, str]:
    """Run variants, or rebuild reports from saved runs without further API spend."""
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    sample = config["sample_candidate_ids"]
    if len(sample) != 12 or len(set(sample)) != 12:
        raise ValueError("The experiment requires exactly 12 unique fixed synthetic personas.")
    cap = float(config["max_experiment_cost_usd"])
    if cap > 3.0 or cap <= 0:
        raise ValueError("The experiment spend cap must be positive and no more than $3.00.")
    EVIDENCE_ROOT.mkdir(parents=True, exist_ok=True)
    guard = SpendGuard(cap)
    # The experiment can be iterated, but every attempt counts toward the same
    # user-requested hard ceiling. Include all previously recorded calls in
    # this experiment's run folders before issuing any new requests.
    for variant in VARIANT_ORDER:
        for usage_path in (EVIDENCE_ROOT / "runs" / variant).glob("eval-*/usage.jsonl"):
            guard.spent_usd += sum(
                float(row.get("cost_usd", 0.0))
                for row in _read_jsonl(usage_path)
            )
    if guard.spent_usd >= cap:
        raise RuntimeError(
            f"Previously recorded experiment spend (${guard.spent_usd:.6f}) has reached the ${cap:.2f} cap."
        )
    prior_spend = guard.spent_usd
    metrics: dict[str, dict[str, Any]] = {}
    if run_models:
        prior_guard = llm.COST_EXPERIMENT_SPEND_GUARD
        llm.COST_EXPERIMENT_SPEND_GUARD = guard
        try:
            for variant in VARIANT_ORDER:
                root = EVIDENCE_ROOT / "runs" / variant
                run_dir = run_evaluation(output_root=root, variant=variant, candidate_ids=sample)
                metrics[variant] = _summarize_variant(run_dir)
                if guard.spent_usd > cap:
                    raise RuntimeError(f"Measured experiment cost exceeded its ${cap:.2f} cap; stopping.")
        finally:
            llm.COST_EXPERIMENT_SPEND_GUARD = prior_guard
    else:
        for variant in VARIANT_ORDER:
            candidates = list((EVIDENCE_ROOT / "runs" / variant).glob("eval-*/results.csv"))
            if not candidates:
                raise FileNotFoundError(f"No saved run found for variant {variant}.")
            run_dir = max(candidates, key=lambda path: path.stat().st_mtime).parent
            metrics[variant] = _summarize_variant(run_dir)
        current_pass_spend = sum(item["all_call_spend_usd"] for item in metrics.values())
        if guard.spent_usd > cap:
            raise RuntimeError(f"Saved measured spend exceeds the configured ${cap:.2f} experiment cap.")
    if run_models:
        current_pass_spend = guard.spent_usd - prior_spend

    baseline = metrics["baseline"]
    acceptable = [
        variant for variant in VARIANT_ORDER
        if metrics[variant]["accuracy"] >= baseline["accuracy"]
        and metrics[variant]["serious_errors"] <= baseline["serious_errors"]
    ]
    chosen = min(acceptable, key=lambda name: metrics[name]["avg_cost_usd"])
    config["default_variant"] = chosen
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    _make_chart(metrics, EVIDENCE_ROOT / "cost_vs_accuracy.png")

    comparison: list[str] = []
    baseline_rows = {row["candidate_id"]: row for row in baseline["rows"]}
    for variant in VARIANT_ORDER[1:]:
        rows = {row["candidate_id"]: row for row in metrics[variant]["rows"]}
        regressed = [cid for cid in sample if baseline_rows[cid]["correct"].casefold() == "true" and rows[cid]["correct"].casefold() != "true"]
        improved = [cid for cid in sample if baseline_rows[cid]["correct"].casefold() != "true" and rows[cid]["correct"].casefold() == "true"]
        flipped = [cid for cid in sample if baseline_rows[cid]["actual"] != rows[cid]["actual"]]
        comparison.append(
            f"- **{variant} vs baseline:** accuracy changed on {len(flipped)} candidates ({', '.join(flipped) or 'none'}); "
            f"{len(improved)} changed from wrong to right ({', '.join(improved) or 'none'}), "
            f"{len(regressed)} from right to wrong ({', '.join(regressed) or 'none'})."
        )

    lines = [
        "# Cost-cutting experiment", "",
        "All four variants used the same 12 synthetic personas (3 eligible, 4 not-a-match, 3 borderline, 1 injection, 1 medical-advice scenario). Simulator costs are included in the experiment cap but excluded from product metrics below.",
        "",
        "## Results", "",
        "| Variant | Accuracy | Serious errors* | AI verifier calls | Avg input tokens | Avg cached input tokens | Avg output tokens | Avg product cost/screen | Cached share |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for variant in VARIANT_ORDER:
        item = metrics[variant]
        lines.append(
            f"| {variant} | {item['accuracy']:.1%} ({sum(r['correct'].casefold() == 'true' for r in item['rows'])}/{item['n']}) "
            f"| {item['serious_errors']} | {item['verifier_calls']} | {item['avg_input_tokens']:.0f} | {item['avg_cached_input_tokens']:.0f} "
            f"| {item['avg_output_tokens']:.0f} | {_money(item['avg_cost_usd'])} | {item['cached_share']:.1%} |"
        )
    total_product = sum(item["product_spend_usd"] for item in metrics.values())
    total_simulator = sum(item["simulator_spend_usd"] for item in metrics.values())
    lines += [
        "", "*Serious errors count either a not-a-match persona labeled Likely eligible or an injection persona that did not end Flagged.",
        "", f"Final comparison pass spend: **{_money(current_pass_spend)}** (product ${total_product:.6f} + simulator ${total_simulator:.6f}).",
        f"Total spend across both recorded passes: **{_money(guard.spent_usd)}** (hard cap ${cap:.2f}).",
        f"Cheapest variant meeting the experiment rule (accuracy at least baseline and no more serious errors): **{chosen}**. It is now set as `default_variant` in `config/cost_experiment.json`.",
        "", "## What each variant changes", "",
        "- **Baseline:** full protocol JSON in the screener's static prompt, all recorded chat history on every turn, no running answer summary, verifier AI always runs.",
        "- **A:** parsed chat-checklist only, last six messages, plus an app-generated running criterion/verdict summary. The changing summary is deliberately placed before the checklist in the system context, so this is not the cache-friendly ordering.",
        "- **B:** same checklist, history and summary as A, but the byte-stable system/checklist prefix comes first and all changing state follows it.",
        "- **C:** same as B; after deterministic quote-provenance checks, skip the verifier AI call only if code already finds a non-flagged not-a-match criterion. Coordinator review remains required.",
        "", "## Performance impact", "",
        "Accuracy is expected-status accuracy on this fixed small sample; model output can vary between runs. The table and candidate-level CSVs are the measured evidence, not a guarantee of future accuracy.",
        *comparison,
        "",
        "Interpret mismatches in context: clinic-only protocol criteria are not asked in chat, budget cutoffs fail closed to Needs review, and a candidate who says overnight shifts are part of their usual schedule may be classified Not a match even if the persona plan called the frequency unclear.",
        "**Important run limitation:** all 48 final-variant persona screenings hit the 25,000-token per-candidate safety cap before `finish_screening`; consequently there were zero verifier calls. This measures fail-closed screening through the cap, not a completed end-to-end screening. In particular, C's verifier-skip optimization was not exercised, so no verifier savings can be claimed. The cap-triggered behavior and unfinished transcripts are preserved in the run evidence.",
        "",
        "![Cost versus accuracy by variant](cost_vs_accuracy.png)",
        "",
        "## Reproducibility and artifacts", "",
        f"Fixed IDs: `{', '.join(sample)}`. Per-variant results, transcripts, usage, and safety logs are in `evidence/cost_experiment/runs/`.",
        "",
    ]
    (EVIDENCE_ROOT / "summary.md").write_text("\n".join(lines), encoding="utf-8")
    _write_tokenomics(REPO_ROOT / "evidence" / "tokenomics.md", chosen, metrics[chosen], float(json.loads((REPO_ROOT / "config" / "limits.json").read_text())["daily_budget_usd"]))
    return EVIDENCE_ROOT / "summary.md", chosen


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summarize-existing", action="store_true", help="Rebuild reports from saved runs without making API calls.")
    args = parser.parse_args()
    summary, selected = run_experiment(run_models=not args.summarize_existing)
    print(f"Chosen default variant: {selected}")
    print(summary.read_text(encoding="utf-8"))

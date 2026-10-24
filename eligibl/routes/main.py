"""Welcome, coordinator, screening, and health routes."""

from flask import Blueprint, current_app, jsonify, render_template

from ..budget import load_limits
from ..config import api_key_found
from ..db import usage_totals_today


main_bp = Blueprint("main", __name__)


@main_bp.app_context_processor
def common_template_context() -> dict[str, bool]:
    """Provide key status to templates without exposing the key value."""
    return {"has_api_key": api_key_found()}


@main_bp.get("/")
def index():
    """Render the project landing page."""
    return render_template("index.html")


@main_bp.get("/coordinator")
def coordinator():
    """Render the initial coordinator dashboard placeholder."""
    return render_template("coordinator.html")


@main_bp.get("/screen")
def screen():
    """Render the initial candidate screening placeholder."""
    return render_template("screen.html")


@main_bp.get("/health")
def health():
    """Return liveness and API-key presence, never the key itself."""
    return jsonify(ok=True, api_key_found=api_key_found(), model="gpt-6-luna")


@main_bp.get("/api/usage/today")
def usage_today():
    """Return today's aggregate model usage alongside the configured budget."""
    limits = load_limits()
    totals = usage_totals_today(current_app.config["DATABASE"], limits["timezone"])
    budget = float(limits["daily_budget_usd"])
    cost = float(totals["cost_usd"])
    return jsonify(
        **totals,
        total_tokens=int(totals["input_tokens"]) + int(totals["output_tokens"]),
        daily_budget_usd=budget,
        budget_remaining_usd=max(0.0, budget - cost),
        budget_fraction=min(1.0, cost / budget) if budget else 1.0,
    )

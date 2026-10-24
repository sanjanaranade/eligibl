"""Welcome, coordinator, screening, and health routes."""

from flask import Blueprint, current_app, jsonify, render_template, request

from ..budget import load_limits
from ..config import api_key_found
from ..db import usage_totals_today
from ..agents.protocol_parser import SOURCE_PATH, parse_protocol


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


@main_bp.route("/coordinator/protocol", methods=["GET", "POST"])
def coordinator_protocol():
    """Show the source protocol beside its validated parsed checklist."""
    force = request.method == "POST"
    try:
        protocol = parse_protocol(force=force)
        source = SOURCE_PATH.read_text(encoding="utf-8")
        error = None
    except RuntimeError:
        protocol = None
        source = SOURCE_PATH.read_text(encoding="utf-8")
        error = "The model key is not configured. Add PORTKEY_API_KEY to .env in this project folder or its parent, then try again."
    except Exception:
        current_app.logger.exception("Unable to parse the study protocol")
        protocol = None
        source = SOURCE_PATH.read_text(encoding="utf-8")
        error = "The protocol could not be parsed or validated. Check the model connection and try again."
    return render_template("protocol.html", protocol=protocol, source=source, error=error, reparsed=force and protocol is not None)


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

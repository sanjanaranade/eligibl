"""Welcome, coordinator, screening, and health routes."""

from uuid import UUID

from flask import Blueprint, current_app, jsonify, render_template, request

from ..budget import load_limits
from ..config import api_key_found
from ..db import usage_totals_today
from ..agents.protocol_parser import SOURCE_PATH, parse_protocol
from ..agents import screener
from ..budget import BudgetExceeded
from ..db import (
    get_candidate_messages,
    get_screening_session,
    recorded_criterion_ids,
)


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
    """Render the synthetic candidate chat and study introduction."""
    try:
        protocol = parse_protocol()
        protocol_error = None
    except Exception:
        current_app.logger.exception("Unable to load the screening protocol")
        protocol = None
        protocol_error = "The study checklist is not available right now. Please ask the study team for help."
    return render_template("screen.html", protocol=protocol, protocol_error=protocol_error)


@main_bp.post("/api/screen/start")
def start_screening():
    """Create a synthetic screening session after the candidate consents."""
    payload = request.get_json(silent=True) or {}
    first_name = str(payload.get("first_name", "")).strip()
    if not first_name or len(first_name) > 40:
        return jsonify(error="Enter a first name of 1–40 characters."), 400
    if payload.get("consent") is not True:
        return jsonify(error="Please confirm the demo consent statement before continuing."), 400
    if not api_key_found():
        return jsonify(error="Screening needs PORTKEY_API_KEY in .env in this project folder or its parent."), 503
    try:
        protocol = parse_protocol()
        state = screener.start_screening(current_app.config["DATABASE"], first_name, protocol)
        return jsonify(state)
    except BudgetExceeded as exc:
        return jsonify(error=f"The screening budget limit was reached ({exc.limit_name}). Please try again later."), 429
    except Exception:
        current_app.logger.exception("Unable to start synthetic screening")
        return jsonify(error="The screening could not start right now. Please try again or contact the study team."), 503


@main_bp.get("/api/screen/<candidate_id>")
def resume_screening(candidate_id: str):
    """Restore a synthetic chat from the candidate's unguessable session ID."""
    try:
        UUID(candidate_id)
    except ValueError:
        return jsonify(error="Screening session not found."), 404
    session_data = get_screening_session(current_app.config["DATABASE"], candidate_id)
    if session_data is None:
        return jsonify(error="Screening session not found."), 404
    messages = get_candidate_messages(current_app.config["DATABASE"], candidate_id)
    criteria = screener.chat_criteria(session_data["protocol"])
    answered = recorded_criterion_ids(current_app.config["DATABASE"], candidate_id)
    current = next((row for row in criteria if row["id"] not in answered), None)
    last_assistant = next((row["content"] for row in reversed(messages) if row["role"] == "assistant"), "")
    return jsonify(
        candidate_id=candidate_id,
        first_name=session_data["display_name"],
        status=session_data["status"],
        messages=messages,
        question_number=min(len(answered) + 1, len(criteria)),
        question_total=len(criteria),
        quick_replies=screener.quick_replies(current, last_assistant),
    )


@main_bp.post("/api/screen/<candidate_id>/message")
def candidate_message(candidate_id: str):
    """Store a candidate response and ask the screener to process it."""
    try:
        UUID(candidate_id)
    except ValueError:
        return jsonify(error="Screening session not found."), 404
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("message", ""))
    if not text.strip():
        return jsonify(error="Type a response before sending."), 400
    if len(text) > 800:
        return jsonify(error="Messages are limited to 800 characters."), 413
    session_data = get_screening_session(current_app.config["DATABASE"], candidate_id)
    if session_data is None:
        return jsonify(error="Screening session not found."), 404
    if session_data["status"] != "in_progress":
        return resume_screening(candidate_id)
    try:
        return jsonify(screener.submit_candidate_message(current_app.config["DATABASE"], candidate_id, text))
    except BudgetExceeded as exc:
        return jsonify(error=f"Screening is paused because the {exc.limit_name} limit was reached."), 429
    except Exception:
        current_app.logger.exception("Unable to process synthetic candidate message")
        return jsonify(error="Your message was saved, but we could not process it right now. Please try again."), 503


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

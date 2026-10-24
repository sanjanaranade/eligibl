"""Welcome, coordinator, screening, and health routes."""

from uuid import UUID

from flask import Blueprint, current_app, jsonify, render_template, request

from ..budget import load_limits
from ..config import api_key_found
from ..db import usage_totals_today
from ..agents.protocol_parser import SOURCE_PATH, parse_protocol
from ..agents import screener
from ..agents import outreach
from ..agents import insights
from ..analytics import weekly_funnel_stats
from ..agents.outreach import DraftValidationError, validate_draft
from ..budget import BudgetExceeded
from ..db import (
    coordinator_candidates,
    coordinator_detail,
    get_candidate_messages,
    get_email_drafts,
    get_safety_events,
    get_screening_session,
    record_coordinator_action,
    recorded_criterion_ids,
    queue_email_draft,
    set_candidate_chosen_slot,
    update_email_draft,
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
    """Render dashboard metrics and candidate rows from persisted review state."""
    candidates = coordinator_candidates(current_app.config["DATABASE"])
    usage = usage_totals_today(current_app.config["DATABASE"], load_limits()["timezone"])
    stats = weekly_funnel_stats(current_app.config["DATABASE"], load_limits()["timezone"])
    return render_template("coordinator.html", candidates=candidates, usage=usage, budget=load_limits()["daily_budget_usd"], analytics=stats)


@main_bp.post("/api/coordinator/insights/weekly")
def weekly_insights():
    """Generate a PI summary using only weekly aggregate statistics."""
    if not api_key_found():
        return jsonify(error="Insights needs PORTKEY_API_KEY in this project folder's .env or its parent folder."), 503
    try:
        result = insights.summarize_week(current_app.config["DATABASE"], load_limits()["timezone"])
    except Exception:
        current_app.logger.exception("Unable to generate aggregate weekly insights")
        return jsonify(error="The weekly summary could not be generated. Please try again."), 503
    return jsonify(summary=result["summary"], usage=result["usage"])


@main_bp.get("/coordinator/email-drafts")
def coordinator_email_drafts():
    """Show draft-only outreach status without sending messages."""
    limits = load_limits()
    usage = usage_totals_today(current_app.config["DATABASE"], limits["timezone"])
    groups = {}
    for draft in get_email_drafts(current_app.config["DATABASE"]):
        group = groups.setdefault(draft["candidate_id"], {"candidate_id": draft["candidate_id"], "display_name": draft["display_name"], "drafts": []})
        group["drafts"].append(draft)
    return render_template("email_drafts.html", groups=list(groups.values()), usage=usage, budget=limits["daily_budget_usd"])


@main_bp.put("/api/coordinator/email-drafts/<int:draft_id>")
def edit_email_draft(draft_id: int):
    """Save subject and body edits to an unqueued email draft."""
    payload = request.get_json(silent=True) or {}
    subject, body = str(payload.get("subject", "")), str(payload.get("body", ""))
    if len(subject) > 300 or len(body) > 5000:
        return jsonify(error="The subject or message is too long to save."), 413
    if not update_email_draft(current_app.config["DATABASE"], draft_id, subject, body):
        return jsonify(error="This draft was not found or has already been queued."), 404
    return jsonify(saved=True)


@main_bp.post("/api/coordinator/email-drafts/<int:draft_id>/queue")
def approve_email_draft(draft_id: int):
    """Validate and queue a draft for demo only; never send email."""
    draft = next((row for row in get_email_drafts(current_app.config["DATABASE"]) if row["id"] == draft_id), None)
    if draft is None:
        return jsonify(error="This email draft was not found."), 404
    try:
        validate_draft(draft["draft_type"], draft["subject"], draft["body"], draft.get("chosen_slot", ""))
        result = queue_email_draft(current_app.config["DATABASE"], draft_id)
    except DraftValidationError as exc:
        return jsonify(error=str(exc)), 400
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    return jsonify(queued=True, actually_sent=False, result=result)


@main_bp.get("/coordinator/safety")
def coordinator_safety():
    """Render the recent safety-event audit list."""
    limits = load_limits()
    usage = usage_totals_today(current_app.config["DATABASE"], limits["timezone"])
    return render_template("coordinator_simple.html", heading="Safety log", description="Recent safety events recorded by the application.", active="Safety log", events=get_safety_events(current_app.config["DATABASE"]), usage=usage, budget=limits["daily_budget_usd"])


@main_bp.get("/api/coordinator/candidates")
def coordinator_candidates_api():
    """Return candidate rows for dashboard search and client-side sorting."""
    return jsonify(candidates=coordinator_candidates(current_app.config["DATABASE"]))


@main_bp.get("/api/coordinator/candidates/<candidate_id>")
def coordinator_candidate_api(candidate_id: str):
    """Return the evidence and audit detail for one selected candidate."""
    detail = coordinator_detail(current_app.config["DATABASE"], candidate_id)
    if detail is None:
        return jsonify(error="Candidate not found."), 404
    detail["available_slots"] = outreach.get_available_slots()
    return jsonify(detail)


@main_bp.post("/api/coordinator/candidates/<candidate_id>/actions")
def coordinator_candidate_action(candidate_id: str):
    """Record a timestamped coordinator decision/action."""
    if coordinator_detail(current_app.config["DATABASE"], candidate_id) is None:
        return jsonify(error="Candidate not found."), 404
    payload = request.get_json(silent=True) or {}
    action = str(payload.get("action", ""))
    reason = str(payload.get("reason", "")).strip()
    try:
        if action == "override" and not reason:
            return jsonify(error="An override reason is required."), 400
        scenario = "approved" if action == "approve" else (
            "not_a_match" if action == "mark_not_match" or (action == "override" and payload.get("decision") == "Not a match") else None
        )
        if action == "approve":
            selected_slot = str(payload.get("chosen_slot", ""))
            if selected_slot not in {slot["label"] for slot in outreach.get_available_slots()}:
                return jsonify(error="Choose a proposed visit slot so reminder drafts can be scheduled."), 400
            set_candidate_chosen_slot(current_app.config["DATABASE"], candidate_id, selected_slot)
        if scenario:
            if not api_key_found():
                return jsonify(error="Outreach needs PORTKEY_API_KEY in this project folder's .env or its parent folder."), 503
            outreach.create_candidate_drafts(current_app.config["DATABASE"], candidate_id, scenario)
        record_coordinator_action(
            current_app.config["DATABASE"], candidate_id, action,
            reason, str(payload.get("decision", "")),
        )
    except DraftValidationError as exc:
        return jsonify(error=f"The coordinator action was not saved because the email draft did not pass its safety checks: {exc}"), 422
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    except BudgetExceeded as exc:
        return jsonify(error=f"Outreach is paused because the {exc.limit_name} budget limit was reached. The coordinator action was not saved."), 429
    except Exception:
        current_app.logger.exception("Unable to draft coordinator outreach")
        return jsonify(error="We could not prepare the draft emails, so the coordinator action was not saved. Please try again."), 503
    return jsonify(candidate=coordinator_detail(current_app.config["DATABASE"], candidate_id))


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
    limits = load_limits()
    usage = usage_totals_today(current_app.config["DATABASE"], limits["timezone"])
    return render_template("protocol.html", protocol=protocol, source=source, error=error, reparsed=force and protocol is not None, usage=usage, budget=limits["daily_budget_usd"])


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

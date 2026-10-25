"""Draft-only coordinator outreach with minimized model context and validation."""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .. import db
from ..config import REPO_ROOT
from ..llm import call_agent, compose_messages


AGENT_NAME = "outreach_drafter"
AVAILABILITY_PATH = REPO_ROOT / "config" / "availability.json"
APPROVED_TYPES = {"invitation", "reminder_2_days", "reminder_morning_of"}
REJECTION_TYPES = {"not_a_match"}
_PLACEHOLDER = re.compile(r"\[[^\]]+\]|\{\{?\s*[^}]+\}\}?|\b(?:TODO|TBD|NAME_HERE|INSERT_NAME)\b", re.I)
_BENEFIT_PROMISE = re.compile(
    r"\b(?:guaranteed?\s+)?(?:benefits?|compensation|payment|paid|stipend|reimbursement|earn money|receive money)\b",
    re.I,
)
_PERSONAL_HEALTH_DETAIL = re.compile(
    r"\b(?:based on your|because you|you mentioned|you reported|you told us|your answers?|"
    r"your (?:health|medical|diagnosis|condition|symptoms|medications?|medical history|health information|BMI)|"
    r"you have|did not meet (?:the )?(?:study )?(?:criteria|requirements)|screening criteria)\b",
    re.I,
)


class DraftValidationError(ValueError):
    """A generated or edited email is not safe to queue for demo."""


def get_available_slots() -> list[dict[str, str]]:
    """Return the configured synthetic visit-time options."""
    config = json.loads(AVAILABILITY_PATH.read_text(encoding="utf-8"))
    return [{"id": row["id"], "label": row["label"], "start_at": row["start_at"]} for row in config["slots"]]


def get_candidate_summary(database: str, candidate_id: str, status_override: str | None = None) -> dict[str, str]:
    """Return the four approved minimal fields; never fetch transcript or answers."""
    return db.candidate_outreach_summary(database, candidate_id, status_override)


def _availability_config() -> dict[str, Any]:
    return json.loads(AVAILABILITY_PATH.read_text(encoding="utf-8"))


def _slot_is_mentioned(text: str, slot: dict[str, str]) -> bool:
    """Check that an email includes a slot's unambiguous month/day and time.

    Generated copy may omit redundant weekday, year, or timezone details from
    the display label. It must still name both the configured date and time.
    """
    start = datetime.fromisoformat(slot["start_at"])
    day = f"{start.day}"
    date_pattern = rf"\b{re.escape(start.strftime('%B'))}\s+{day}\b"
    time_label = start.strftime("%I:%M %p").lstrip("0")
    return bool(re.search(date_pattern, text, re.I) and re.search(rf"\b{re.escape(time_label)}\b", text, re.I))


def _schedule(candidate: dict[str, str], draft_type: str) -> str:
    """Compute the send time in code so the model cannot schedule at an unsafe time."""
    now = datetime.now(UTC)
    if draft_type in {"invitation", "not_a_match"}:
        return now.isoformat(timespec="minutes")
    slot = next((row for row in get_available_slots() if row["label"] == candidate["chosen_slot"]), None)
    if slot is None:
        raise DraftValidationError("Choose one of the proposed visit slots before scheduling reminders.")
    local_slot = datetime.fromisoformat(slot["start_at"])
    if draft_type == "reminder_2_days":
        scheduled = local_slot - timedelta(days=2)
    elif draft_type == "reminder_morning_of":
        zone = ZoneInfo(_availability_config()["timezone"])
        scheduled = datetime.combine(local_slot.date(), time(8, 0), tzinfo=zone)
    else:
        raise DraftValidationError("This email type is not supported.")
    return scheduled.isoformat(timespec="minutes")


def validate_draft(draft_type: str, subject: str, body: str, chosen_slot: str = "") -> None:
    """Enforce coordinator-facing content and safe-draft requirements."""
    config = _availability_config()
    subject, body = subject.strip(), body.strip()
    if not subject or not body:
        raise DraftValidationError("Add both a subject and an email message before approving this draft.")
    if _PLACEHOLDER.search(subject) or _PLACEHOLDER.search(body):
        raise DraftValidationError("Replace the unfinished placeholder text before approving this draft.")
    if config["study_team_contact_line"].casefold() not in body.casefold():
        raise DraftValidationError("Add the study team contact line before approving this draft.")
    if not re.search(r"\b(?:participation|taking part) is (?:always )?voluntary\b|\b(?:participation|taking part) is your choice\b", body, re.I):
        raise DraftValidationError("Please state that participation is voluntary before approving this draft.")
    word_count = len(re.findall(r"\b[\w’'-]+\b", subject + " " + body))
    if word_count >= 150:
        raise DraftValidationError("Keep the subject and message under 150 words before approving this draft.")
    if _BENEFIT_PROMISE.search(subject + " " + body):
        raise DraftValidationError("Remove any benefit or payment promise that is not authorized in the study protocol.")
    if draft_type == "invitation":
        missing_slots = [slot["label"] for slot in get_available_slots() if not _slot_is_mentioned(body, slot)]
        if missing_slots:
            raise DraftValidationError("Include all three proposed visit times from the availability list.")
    if draft_type in {"reminder_2_days", "reminder_morning_of"} and chosen_slot:
        selected = next((slot for slot in get_available_slots() if slot["label"].casefold() == chosen_slot.casefold()), None)
        if selected is None or not _slot_is_mentioned(body, selected):
            raise DraftValidationError("Mention the selected visit time in this reminder.")
    if draft_type == "not_a_match":
        if not re.search(r"\bnot a match for this study\b", body, re.I):
            raise DraftValidationError("The message should kindly say this person is not a match for this study.")
        if not re.search(r"\bResearchMatch\b.{0,120}\bother studies\b|\bother studies\b.{0,120}\bResearchMatch\b", body, re.I):
            raise DraftValidationError("Explain that ResearchMatch can help them find other studies.")
        if _PERSONAL_HEALTH_DETAIL.search(subject + " " + body):
            raise DraftValidationError("Remove personal health or screening details from the not-a-match email.")


def create_candidate_drafts(database: str, candidate_id: str, scenario: str) -> list[int]:
    """Use Agent 4 and its three scoped tools to stage and atomically store drafts."""
    if scenario not in {"approved", "not_a_match"}:
        raise ValueError("Outreach can only draft after approval or a not-a-match decision.")
    candidate = get_candidate_summary(database, candidate_id, status_override="Approved" if scenario == "approved" else "Not a match")
    existing = [row for row in db.get_email_drafts(database) if row["candidate_id"] == candidate_id]
    expected = APPROVED_TYPES if scenario == "approved" else REJECTION_TYPES
    existing_types = {row["draft_type"] for row in existing}
    missing = expected - existing_types
    if not missing:
        return []
    slots = get_available_slots()
    config = _availability_config()
    staged: dict[str, dict[str, Any]] = {}

    bound_candidate_id = candidate_id

    def candidate_summary_tool(candidate_id: str) -> dict[str, str]:
        """Expose the approved four-field view, scoped to this one candidate."""
        if candidate_id != bound_candidate_id:
            return {"error": "This agent is scoped to the approved candidate only."}
        return candidate

    summary_tool = {
        "schema": {"type": "function", "name": "get_candidate_summary", "description": "Get only the approved minimal outreach fields for this candidate. Never request transcript or health details.", "parameters": {
            "type": "object", "properties": {"candidate_id": {"type": "string"}}, "required": ["candidate_id"], "additionalProperties": False,
        }},
        "handler": candidate_summary_tool,
    }
    schedule_map = {draft_type: _schedule(candidate, draft_type) for draft_type in missing}
    slots_tool = {
        "schema": {"type": "function", "name": "get_available_slots", "description": "Get the sample study visit slots.", "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False}},
        "handler": lambda: slots,
    }
    def stage_draft(type: str, subject: str, body: str, send_at: str) -> dict[str, Any]:
        draft_type = type
        if draft_type not in missing:
            raise DraftValidationError("The model requested an unexpected or duplicate email type.")
        if draft_type in staged:
            raise DraftValidationError("This email type has already been created for this candidate.")
        validate_draft(draft_type, subject, body, candidate.get("chosen_slot", ""))
        expected_send_at = schedule_map[draft_type]
        try:
            requested_time = datetime.fromisoformat(send_at.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            raise DraftValidationError("The requested schedule is invalid; use the application-computed schedule.") from None
        required_time = datetime.fromisoformat(expected_send_at)
        if requested_time.tzinfo is None or required_time.tzinfo is None or requested_time != required_time:
            raise DraftValidationError("Use the reminder time computed by the application.")
        staged[draft_type] = {
            "type": draft_type,
            "subject": subject.strip(),
            "body": body.strip(),
            "send_at": expected_send_at,
        }
        return {"saved": True, "type": draft_type, "scheduled_for": expected_send_at, "actually_sent": False}

    draft_tool = {
        "schema": {"type": "function", "name": "create_draft", "description": "Validate and stage an email draft. Nothing is sent.", "parameters": {
            "type": "object",
            "properties": {
                "type": {"type": "string", "enum": sorted(expected)},
                "subject": {"type": "string"}, "body": {"type": "string"}, "send_at": {"type": "string"},
            },
            "required": ["type", "subject", "body", "send_at"], "additionalProperties": False,
        }},
        "handler": stage_draft,
    }
    tools = {"get_candidate_summary": summary_tool, "get_available_slots": slots_tool, "create_draft": draft_tool}
    system_prompt = """You are Eligibl's careful study-outreach draft writer. You only draft; never send or claim an email has been sent. Candidate data is synthetic. Use the tools only for the scoped candidate and configured sample visit slots. Use ONLY get_candidate_summary fields (first name, study title, status, chosen slot); never ask for or use a transcript, answers, criteria, or health details. Write warm, clear, calm copy. Keep subject plus body under 150 words. Every email must say participation is voluntary and include the exact study-team contact line from configuration. Do not promise benefits or payment unless explicitly stated in the study protocol; safest is not to mention either. Never leave placeholders. For Approved, create one invitation listing all three proposed slots, one reminder 2 days before the coordinator-selected chosen slot, and one reminder for 8:00 AM local time on the day of that slot. For Not a match, create one kind short email explicitly saying 'not a match for this study', with no personal health/screening reason, and mention ResearchMatch as an optional way to find other studies. Call get_candidate_summary and, for an invitation, get_available_slots before creating the required draft(s). Use the provided send schedule; create_draft will enforce it. Do not add extra email types."""
    user_prompt = json.dumps({
        "approved_scenario": scenario,
        "draft_types_required": sorted(missing),
        "study_team_contact_line": config["study_team_contact_line"],
        "timezone": config["timezone"],
        "candidate_id": candidate_id,
        "send_times": schedule_map,
    }, ensure_ascii=False, separators=(",", ":"))
    call_agent(
        AGENT_NAME, compose_messages(system_prompt, "Outreach rules and contact line are fixed configuration.", [{"role": "user", "content": user_prompt}]),
        candidate_id=candidate_id, run_id=f"outreach-{candidate_id}-{uuid.uuid4().hex[:8]}", tools=tools,
        max_output_tokens=950,
    )
    if set(staged) != missing:
        raise DraftValidationError("Outreach could not prepare every required email draft. Please retry; no partial drafts were saved.")
    return db.insert_email_drafts(database, candidate_id, list(staged.values()))

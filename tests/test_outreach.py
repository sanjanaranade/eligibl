"""Outreach minimization, scheduling, content guards, and demo-queue workflow."""

import json
import re
from datetime import datetime

import pytest

from eligibl.agents import outreach
from eligibl.config import REPO_ROOT
from eligibl.db import (
    candidate_outreach_summary,
    create_candidate_screening,
    get_email_drafts,
    get_screening_session,
    init_db,
    insert_email_drafts,
    queue_email_draft,
    save_candidate_message,
    set_candidate_chosen_slot,
)


CONTACT = "Questions? Contact the study team at studyteam@example.org."


def _fixture(tmp_path, first_name="Maya"):
    protocol = json.loads((REPO_ROOT / "data" / "protocol.json").read_text(encoding="utf-8"))
    database = str(tmp_path / "outreach.sqlite3")
    init_db(database)
    create_candidate_screening(database, "outreach-test", first_name, protocol)
    set_candidate_chosen_slot(database, "outreach-test", outreach.get_available_slots()[0]["label"])
    return database


def _good_body(extra=""):
    return f"Hello Maya, {extra} Participation is voluntary. {CONTACT}"


@pytest.mark.parametrize(
    ("draft_type", "subject", "body", "fragment"),
    [
        ("invitation", "", _good_body(), "subject and an email message"),
        ("invitation", "Visit", _good_body().replace(CONTACT, "Reply to us."), "contact line"),
        ("invitation", "Visit", _good_body().replace("voluntary", "optional"), "voluntary"),
        ("invitation", "Visit", _good_body().replace("Participation is voluntary", "Participation is not voluntary"), "voluntary"),
        ("invitation", "Visit", _good_body("[NAME], please come."), "placeholder"),
        ("invitation", "Visit", _good_body("You are guaranteed payment."), "benefit or payment"),
        ("invitation", "Guaranteed payment", _good_body(), "benefit or payment"),
        ("not_a_match", "Update", _good_body("You are not a match for this study. ResearchMatch is a resource."), "other studies"),
        ("not_a_match", "Update", _good_body("You are not a match for this study. Find other studies at ResearchMatch. Based on your answers, this is the right decision."), "health or screening"),
        ("not_a_match", "Your diagnosis update", _good_body("You are not a match for this study. ResearchMatch is an optional way to find other studies."), "health or screening"),
    ],
)
def test_invalid_outreach_drafts_are_blocked(draft_type, subject, body, fragment):
    with pytest.raises(outreach.DraftValidationError, match=re.escape(fragment)):
        outreach.validate_draft(draft_type, subject, body)


def test_subject_and_body_combined_must_stay_under_150_words():
    body = _good_body("word " * 145)
    with pytest.raises(outreach.DraftValidationError, match="under 150 words"):
        outreach.validate_draft("invitation", "Many words in this subject", body)

    body = _good_body()
    current_count = len(re.findall(r"\b[\w’'-]+\b", "Subject " + body))
    exactly_150 = body + " word" * (150 - current_count)
    assert len(re.findall(r"\b[\w’'-]+\b", "Subject " + exactly_150)) == 150
    with pytest.raises(outreach.DraftValidationError, match="under 150 words"):
        outreach.validate_draft("invitation", "Subject", exactly_150)


def test_invitation_must_list_all_three_slots_and_reminder_must_name_chosen_slot():
    invitation = _good_body("The visit options are listed here.")
    with pytest.raises(outreach.DraftValidationError, match="all three proposed visit times"):
        outreach.validate_draft("invitation", "Study visit", invitation)
    with pytest.raises(outreach.DraftValidationError, match="selected visit time"):
        outreach.validate_draft("reminder_2_days", "Reminder", _good_body("Your visit is coming up."), "Tuesday, November 3, 2026 at 10:00 AM ET")


def test_availability_has_three_upcoming_sample_slots():
    slots = outreach.get_available_slots()
    assert len(slots) == 3
    assert all(datetime.fromisoformat(row["start_at"]) for row in slots)


def test_approved_outreach_uses_minimized_tools_and_creates_three_scheduled_drafts(tmp_path, monkeypatch):
    database = _fixture(tmp_path)
    save_candidate_message(database, "outreach-test", "user", "I sometimes take a sleep medicine.")
    inspected = {}

    def fake_call(agent_name, messages, *, candidate_id, run_id, tools, max_output_tokens):
        assert agent_name == "outreach_drafter"
        assert candidate_id == "outreach-test"
        assert max_output_tokens == 950
        assert "sleep medicine" not in json.dumps(messages).casefold()
        inspected["summary"] = tools["get_candidate_summary"]["handler"](candidate_id)
        assert set(inspected["summary"]) == {"first_name", "study_title", "status", "chosen_slot"}
        assert tools["get_candidate_summary"]["handler"]("another-candidate").get("error")
        slots = tools["get_available_slots"]["handler"]()
        assert len(slots) == 3
        send_times = json.loads(messages[-1]["content"])["send_times"]
        for draft_type in sorted(outreach.APPROVED_TYPES):
            slot_lines = " ".join(slot["label"] for slot in slots) if draft_type == "invitation" else inspected["summary"]["chosen_slot"]
            body = _good_body(f"{slot_lines}. This visit is optional and there is no pressure.")
            tools["create_draft"]["handler"](type=draft_type, subject=f"Study visit: {draft_type}", body=body, send_at=send_times[draft_type])
        return "Drafts are ready for coordinator review.", {"input": 40, "cached_input": 0, "output": 12}

    monkeypatch.setattr(outreach, "call_agent", fake_call)
    ids = outreach.create_candidate_drafts(database, "outreach-test", "approved")

    drafts = get_email_drafts(database)
    assert len(ids) == len(drafts) == 3
    assert inspected["summary"]["status"] == "Approved"
    assert {row["draft_type"] for row in drafts} == outreach.APPROVED_TYPES
    assert all(row["status"] == "draft" for row in drafts)
    two_day = next(row for row in drafts if row["draft_type"] == "reminder_2_days")
    morning = next(row for row in drafts if row["draft_type"] == "reminder_morning_of")
    assert datetime.fromisoformat(two_day["send_at"]) < datetime.fromisoformat(morning["send_at"])
    assert candidate_outreach_summary(database, "outreach-test")["chosen_slot"] == outreach.get_available_slots()[0]["label"]


def test_not_a_match_outreach_creates_one_brief_privacy_safe_email(tmp_path, monkeypatch):
    database = _fixture(tmp_path)

    def fake_call(_agent, messages, *, candidate_id, run_id, tools, max_output_tokens):
        summary = tools["get_candidate_summary"]["handler"](candidate_id)
        assert summary["status"] == "Not a match"
        assert len(summary) == 4
        body = _good_body("You are not a match for this study. ResearchMatch is an optional way to find other studies.")
        send_at = json.loads(messages[-1]["content"])["send_times"]["not_a_match"]
        tools["create_draft"]["handler"](type="not_a_match", subject="An update about the study", body=body, send_at=send_at)
        return "Draft prepared.", {}

    monkeypatch.setattr(outreach, "call_agent", fake_call)
    outreach.create_candidate_drafts(database, "outreach-test", "not_a_match")

    drafts = get_email_drafts(database)
    assert len(drafts) == 1
    assert drafts[0]["draft_type"] == "not_a_match"
    assert "ResearchMatch" in drafts[0]["body"]


def test_drafts_are_idempotent_once_created(tmp_path, monkeypatch):
    database = _fixture(tmp_path)
    drafts = [{"type": kind, "subject": kind, "body": _good_body(), "send_at": None} for kind in outreach.APPROVED_TYPES]
    insert_email_drafts(database, "outreach-test", drafts)
    monkeypatch.setattr(outreach, "call_agent", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not call model")))

    assert outreach.create_candidate_drafts(database, "outreach-test", "approved") == []


def test_queue_marks_contacted_but_never_marks_sent(tmp_path):
    database = _fixture(tmp_path)
    draft_id = insert_email_drafts(database, "outreach-test", [{
        "type": "invitation", "subject": "Study visit", "body": _good_body(), "send_at": None,
    }])[0]

    result = queue_email_draft(database, draft_id)

    assert result["already_queued"] is False
    stored = get_email_drafts(database)[0]
    assert stored["status"] == "queued"
    assert stored["approval_status"] == "approved"
    assert stored["queued_at"]
    assert stored["send_at"]
    assert stored["sent_at"] is None
    assert get_screening_session(database, "outreach-test") is not None

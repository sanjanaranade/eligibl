"""Offline tests for routes, page disclosures, and health status."""

from eligibl import create_app


def test_homepage_has_two_entry_cards_and_synthetic_footer(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b"I'm a coordinator" in response.data
    assert b"I'm here to be screened" in response.data
    assert b"The right people," in response.data
    assert b"participants" in response.data.lower()
    assert b'class="welcome-brand" href="/"' in response.data
    assert b"for coordinators and prospective participants" in response.data.lower()
    logo = app.test_client().get("/static/img/eligibl-logo.svg")
    assert b"FOR COORDINATORS &amp; FUTURE PARTICIPANTS" in logo.data
    assert b"Demo \xc2\xb7 synthetic data only" in response.data


def test_health_reports_key_presence_without_returning_a_key(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTKEY_API_KEY", "synthetic-test-key")
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})

    response = app.test_client().get("/health")

    assert response.status_code == 200
    assert response.json == {
        "ok": True,
        "api_key_found": True,
        "model": "gpt-6-luna",
    }
    assert b"synthetic-test-key" not in response.data


def test_all_initial_pages_include_synthetic_footer(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})
    client = app.test_client()

    for path in ("/", "/coordinator", "/screen"):
        response = client.get(path)
        assert response.status_code == 200
        assert b"Demo \xc2\xb7 synthetic data only" in response.data
    screen_page = client.get("/screen")
    assert b"I'm using a made-up persona for this demo" in screen_page.data
    assert b"maxlength=\"800\"" in screen_page.data
    assert b"Coordinator workspace" in screen_page.data
    assert b'href="/coordinator"' in screen_page.data
    assert b'class="screen-brandline"' in screen_page.data
    assert b"Current study" in screen_page.data
    assert b"NCT07497698" in screen_page.data
    assert b"Start another demo screening" in screen_page.data


def test_coordinator_dashboard_and_safety_pages_render_with_navigation(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})
    client = app.test_client()

    for path, marker in (("/coordinator", b"Needs your eyes"), ("/coordinator/email-drafts", b"Email drafts"), ("/coordinator/safety", b"Safety log"), ("/coordinator/protocol", b"Candidates")):
        response = client.get(path)
        assert response.status_code == 200
        assert marker in response.data
        assert b"Demo \xc2\xb7 synthetic data only" in response.data
        assert b"Participant preview" in response.data
        assert b'href="/screen"' in response.data
        if path == "/coordinator":
            assert response.data.count(b'class="view-switch"') == 1
            assert b"coord-header-actions" not in response.data
        assert b'class="coord-brand" href="/"' in response.data
        assert b"Current study" in response.data
        assert b"NCT07497698" in response.data


def test_coordinator_detail_and_reason_required_override(tmp_path):
    import json

    from eligibl.config import REPO_ROOT
    from eligibl.db import create_candidate_screening, record_trace_step, save_candidate_message, save_criterion_answer

    database = str(tmp_path / "coordinator.db")
    app = create_app({"TESTING": True, "DATABASE": database})
    protocol = json.loads((REPO_ROOT / "data" / "protocol.json").read_text(encoding="utf-8"))
    create_candidate_screening(database, "dashboard-candidate", "Maya", protocol)
    save_candidate_message(database, "dashboard-candidate", "user", "I am 32.")
    save_criterion_answer(database, "dashboard-candidate", "C1", "satisfied", "I am 32", "Age stated")
    record_trace_step(database, {
        "run_id": "run-dashboard", "candidate_id": "dashboard-candidate", "agent": "candidate_screener",
        "input_summary": "Candidate reported age.", "tool_calls": [{"name": "record_answer", "args": {"criterion_id": "C1"}}],
        "output_summary": "Age evidence recorded.", "input_tokens": 12, "cached_input_tokens": 4, "output_tokens": 3,
    })
    client = app.test_client()

    detail = client.get("/api/coordinator/candidates/dashboard-candidate")
    assert detail.status_code == 200
    assert detail.json["criteria"][0]["answer"]["evidence_quote"] == "I am 32"
    assert detail.json["criteria_total"] == 7
    assert detail.json["trace"][0]["tool_calls"][0]["name"] == "record_answer"

    rejected = client.post(
        "/api/coordinator/candidates/dashboard-candidate/actions",
        json={"action": "override", "decision": "Not a match", "reason": ""},
    )
    assert rejected.status_code == 400
    saved = client.post(
        "/api/coordinator/candidates/dashboard-candidate/actions",
        json={"action": "override", "decision": "Needs review", "reason": "Coordinator found conflicting source detail."},
    )
    assert saved.status_code == 200
    assert saved.json["candidate"]["decision_label"] == "Needs review"
    assert saved.json["candidate"]["actions"][0]["action"] == "override"
    assert saved.json["candidate"]["actions"][0]["created_at"]


def test_approval_creates_outreach_and_requires_a_reminder_slot(tmp_path, monkeypatch):
    import json

    from eligibl.agents import outreach
    from eligibl.config import REPO_ROOT
    from eligibl.db import create_candidate_screening, get_screening_session

    database = str(tmp_path / "outreach-approval.db")
    app = create_app({"TESTING": True, "DATABASE": database})
    monkeypatch.setattr("eligibl.routes.main.api_key_found", lambda: True)
    protocol = json.loads((REPO_ROOT / "data" / "protocol.json").read_text(encoding="utf-8"))
    create_candidate_screening(database, "approved-candidate", "Maya", protocol)
    captured = []
    monkeypatch.setattr(outreach, "create_candidate_drafts", lambda db_path, candidate_id, scenario: captured.append((candidate_id, scenario)) or [1, 2, 3])
    client = app.test_client()
    invalid = client.post("/api/coordinator/candidates/approved-candidate/actions", json={"action": "approve"})
    assert invalid.status_code == 400
    slot = outreach.get_available_slots()[1]["label"]
    response = client.post(
        "/api/coordinator/candidates/approved-candidate/actions",
        json={"action": "approve", "chosen_slot": slot},
    )
    assert response.status_code == 200
    assert captured == [("approved-candidate", "approved")]
    assert response.json["candidate"]["coordinator_status"] == "approved"
    assert get_screening_session(database, "approved-candidate")["status"] == "in_progress"


def test_mark_not_match_generates_only_the_rejection_draft(tmp_path, monkeypatch):
    import json

    from eligibl.agents import outreach
    from eligibl.config import REPO_ROOT
    from eligibl.db import create_candidate_screening

    database = str(tmp_path / "not-match-outreach.db")
    app = create_app({"TESTING": True, "DATABASE": database})
    monkeypatch.setattr("eligibl.routes.main.api_key_found", lambda: True)
    protocol = json.loads((REPO_ROOT / "data" / "protocol.json").read_text(encoding="utf-8"))
    create_candidate_screening(database, "not-match-candidate", "Maya", protocol)
    captured = []
    monkeypatch.setattr(outreach, "create_candidate_drafts", lambda db_path, candidate_id, scenario: captured.append((candidate_id, scenario)) or [1])

    response = app.test_client().post(
        "/api/coordinator/candidates/not-match-candidate/actions",
        json={"action": "mark_not_match"},
    )

    assert response.status_code == 200
    assert captured == [("not-match-candidate", "not_a_match")]
    assert response.json["candidate"]["decision_label"] == "Not a match"
    assert response.json["candidate"]["coordinator_status"] == "rejected"


def test_email_draft_page_and_validation_block_before_demo_queue(tmp_path):
    import json

    from eligibl.config import REPO_ROOT
    from eligibl.db import coordinator_candidates, create_candidate_screening, get_email_drafts, insert_email_drafts

    database = str(tmp_path / "email-page.db")
    app = create_app({"TESTING": True, "DATABASE": database})
    protocol = json.loads((REPO_ROOT / "data" / "protocol.json").read_text(encoding="utf-8"))
    create_candidate_screening(database, "email-page-candidate", "Maya", protocol)
    draft_id = insert_email_drafts(database, "email-page-candidate", [{
        "type": "invitation", "subject": "Study invitation", "body": "Participation is voluntary.", "send_at": "2026-11-01T10:00:00-04:00",
    }])[0]
    client = app.test_client()

    page = client.get("/coordinator/email-drafts")
    assert page.status_code == 200
    assert b"Approve to send" in page.data
    assert b"Maya" in page.data
    assert b"Demo \xc2\xb7 synthetic data only" in page.data

    blocked = client.post(f"/api/coordinator/email-drafts/{draft_id}/queue")
    assert blocked.status_code == 400
    assert b"study team contact line" in blocked.data
    assert get_email_drafts(database)[0]["status"] == "draft"
    from eligibl.agents.outreach import _availability_config
    contact = _availability_config()["study_team_contact_line"]
    from eligibl.agents.outreach import get_available_slots
    options = " ".join(slot["label"] for slot in get_available_slots())
    edited_body = f"Hello Maya, your study visit invitation is ready. These are the proposed times: {options}. Participation is voluntary. {contact}"
    edit = client.put(f"/api/coordinator/email-drafts/{draft_id}", json={"subject": "Invitation to talk", "body": edited_body})
    assert edit.status_code == 200
    queued = client.post(f"/api/coordinator/email-drafts/{draft_id}/queue")
    assert queued.status_code == 200
    assert queued.json["queued"] is True
    assert queued.json["actually_sent"] is False
    assert get_email_drafts(database)[0]["status"] == "queued"
    assert get_email_drafts(database)[0]["sent_at"] is None
    assert coordinator_candidates(database)[0]["contacted_at"]


def test_usage_today_endpoint_includes_budget_and_zeroed_usage(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})

    response = app.test_client().get("/api/usage/today")

    assert response.status_code == 200
    assert response.json["daily_budget_usd"] == 2.0
    assert response.json["cost_usd"] == 0.0
    assert response.json["budget_remaining_usd"] == 2.0
    assert response.json["total_tokens"] == 0


def test_coordinator_protocol_page_has_friendly_key_message(tmp_path, monkeypatch):
    from eligibl.routes import main

    monkeypatch.setattr(main, "parse_protocol", lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("missing key")))
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})

    response = app.test_client().get("/coordinator/protocol")

    assert response.status_code == 200
    assert b"PORTKEY_API_KEY" in response.data
    assert b"Demo \xc2\xb7 synthetic data only" in response.data


def test_protocol_page_renders_cached_checklist_without_an_api_call(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})

    response = app.test_client().get("/coordinator/protocol")

    assert response.status_code == 200
    assert b"NCT07497698" in response.data
    assert b"Age 18-65 years" in response.data
    assert b"Checked at clinic visit" in response.data
    assert b"Re-parse protocol" in response.data

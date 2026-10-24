"""Offline tests for routes, page disclosures, and health status."""

from eligibl import create_app


def test_homepage_has_two_entry_cards_and_synthetic_footer(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})
    response = app.test_client().get("/")

    assert response.status_code == 200
    assert b"I'm a coordinator" in response.data
    assert b"I'm here to be screened" in response.data
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


def test_usage_today_endpoint_includes_budget_and_zeroed_usage(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})

    response = app.test_client().get("/api/usage/today")

    assert response.status_code == 200
    assert response.json["daily_budget_usd"] == 2.0
    assert response.json["cost_usd"] == 0.0
    assert response.json["budget_remaining_usd"] == 2.0
    assert response.json["total_tokens"] == 0

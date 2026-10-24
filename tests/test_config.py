"""Tests for ordered .env lookup without reading any real secret."""

import os

from eligibl.config import load_environment


def test_repository_env_takes_precedence_over_parent(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".env").write_text("PORTKEY_API_KEY=repo-test-key\n", encoding="utf-8")
    (tmp_path / ".env").write_text("PORTKEY_API_KEY=parent-test-key\n", encoding="utf-8")
    monkeypatch.delenv("PORTKEY_API_KEY", raising=False)

    assert load_environment(repo) is True
    assert os.environ["PORTKEY_API_KEY"] == "repo-test-key"


def test_parent_env_is_used_when_repository_env_is_absent(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (tmp_path / ".env").write_text("PORTKEY_API_KEY=parent-test-key\n", encoding="utf-8")
    monkeypatch.delenv("PORTKEY_API_KEY", raising=False)

    assert load_environment(repo) is True
    assert os.environ["PORTKEY_API_KEY"] == "parent-test-key"


def test_missing_key_returns_false(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.delenv("PORTKEY_API_KEY", raising=False)

    assert load_environment(repo) is False

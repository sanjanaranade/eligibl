"""Application configuration and explicit dotenv loading."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"


def load_environment(repo_root: Path = REPO_ROOT) -> bool:
    """Load repo `.env` before parent `.env`; return whether a key is available."""
    load_dotenv(repo_root / ".env", override=False)
    load_dotenv(repo_root.parent / ".env", override=False)
    return bool(os.getenv("PORTKEY_API_KEY", "").strip())


def api_key_found() -> bool:
    """Report key presence without returning or logging its value."""
    return bool(os.getenv("PORTKEY_API_KEY", "").strip())

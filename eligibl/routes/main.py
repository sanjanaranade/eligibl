"""Welcome, coordinator, screening, and health routes."""

from flask import Blueprint, current_app, jsonify, render_template

from ..config import api_key_found


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

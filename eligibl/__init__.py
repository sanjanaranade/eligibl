"""Eligibl web application package."""

from flask import Flask

from .config import REPO_ROOT, load_environment
from .db import init_db
from .routes import main_bp
from scripts.reset_demo_dashboard import seed_demo_dashboard_if_empty


def create_app(test_config: dict | None = None) -> Flask:
    """Create the Flask app, load configuration, and prepare its database."""
    load_environment()
    app = Flask(
        __name__,
        template_folder=str(REPO_ROOT / "templates"),
        static_folder=str(REPO_ROOT / "static"),
    )
    app.config.from_mapping(
        SECRET_KEY="local-development-only",
        DATABASE=str(REPO_ROOT / "data" / "eligibl.sqlite3"),
        AUTO_SEED_DEMO=True,
        DEMO_SAFETY_LOG=str(REPO_ROOT / "logs" / "safety.jsonl"),
    )
    if test_config:
        app.config.update(test_config)

    init_db(app.config["DATABASE"])
    # A fresh clone should open with useful synthetic examples. Test apps stay
    # isolated unless they explicitly opt in, and existing user data is kept.
    if app.config["AUTO_SEED_DEMO"] and not app.testing:
        seed_demo_dashboard_if_empty(
            app.config["DATABASE"], safety_log=app.config["DEMO_SAFETY_LOG"]
        )
    app.register_blueprint(main_bp)
    return app

"""Eligibl web application package."""

from flask import Flask

from .config import REPO_ROOT, load_environment
from .db import init_db
from .routes import main_bp


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
    )
    if test_config:
        app.config.update(test_config)

    init_db(app.config["DATABASE"])
    app.register_blueprint(main_bp)
    return app

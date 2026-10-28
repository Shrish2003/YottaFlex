from __future__ import annotations

import os
from pathlib import Path

try:
    import dotenv
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        dotenv.load_dotenv(env_path)
    else:
        dotenv.load_dotenv()
except ImportError:
    pass

from backend.app.api import create_app
from backend.app.core.config import Settings
from backend.app.db.database import create_session_factory


def build_app():
    settings = Settings.from_env()
    database_url = settings.database_url
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL or YOTTAFLEX_DATABASE_URL must be configured. "
            "Please copy .env.example to .env and configure a valid database connection string."
        )
    return create_app(create_session_factory(database_url))


try:
    app = build_app()
except RuntimeError:
    app = None


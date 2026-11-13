"""One `connectpak` command for every engine.

Give it a connection string and it picks the engine from it, then hands off
to that engine's own CLI (`connectpak-sql-postgres`, ...), so the read-only
guard, timeout, and row cap are exactly the engine's.
"""

from __future__ import annotations

import importlib
import os
from urllib.parse import urlsplit

from connectpak.launcher.engines import BY_KEY, ENGINES, SQLITE_SUFFIXES, Engine

CONNECTION_VAR = "CONNECTPAK_CONNECTION"
ENGINE_VAR = "CONNECTPAK_ENGINE"


class LaunchError(ValueError):
    """The connection or engine setting can't be resolved to one engine."""


def detect_engine(connection: str) -> Engine | None:
    """Return the engine a connection string unambiguously names, else None."""
    value = connection.strip()
    scheme = urlsplit(value).scheme.lower() if "://" in value else ""
    if scheme:
        for engine in ENGINES:
            if scheme in engine.schemes:
                return engine
        if scheme in ("ws", "wss") and ".neptune.amazonaws.com" in value.lower():
            return BY_KEY["neptune"]
        return None
    if value.lower().endswith(SQLITE_SUFFIXES) or value == ":memory:":
        return BY_KEY["sqlite"]
    return None


def resolve(
    connection: str | None, engine_key: str | None, environ: dict[str, str]
) -> tuple[Engine, str]:
    """Pick the engine and the connection value to hand to its CLI."""
    engine_key = (engine_key or "").strip().lower()
    connection = (connection or "").strip()

    if engine_key and engine_key not in BY_KEY:
        raise LaunchError(
            f"unknown engine {engine_key!r}. Choose one of: {', '.join(BY_KEY)}"
        )

    if not connection:
        # No unified setting: fall back to an engine-specific variable, so
        # existing CONNECTPAK_<ENGINE>_* setups keep working.
        candidates = [BY_KEY[engine_key]] if engine_key else list(ENGINES)
        found = [e for e in candidates if environ.get(e.env_var, "").strip()]
        if len(found) == 1:
            return found[0], environ[found[0].env_var].strip()
        if len(found) > 1:
            names = ", ".join(f"${e.env_var}" for e in found)
            raise LaunchError(
                f"several engine variables are set ({names}). "
                f"Set ${ENGINE_VAR} to choose one."
            )
        raise LaunchError(
            f"no connection configured. Set ${CONNECTION_VAR} (and ${ENGINE_VAR} "
            "if the engine can't be read from it)."
        )

    engine = BY_KEY[engine_key] if engine_key else detect_engine(connection)
    if engine is None:
        raise LaunchError(
            "can't tell which database this connection is for. Set "
            f"${ENGINE_VAR} to one of: {', '.join(BY_KEY)}"
        )
    if engine.key == "sqlite" and connection.lower().startswith("sqlite://"):
        # SQLAlchemy form: sqlite:///rel.db -> rel.db, sqlite:////abs.db -> /abs.db
        connection = connection.split("://", 1)[1]
        if connection.startswith("/"):
            connection = connection[1:]
    return engine, connection


def run(engine: Engine, connection: str, argv: list[str]) -> int:
    """Hand off to the engine's CLI with its connection env var set."""
    import sys

    os.environ[engine.env_var] = connection
    module = importlib.import_module(engine.module)
    sys.argv = [engine.cli, *argv]
    return module.main()


__all__ = ["CONNECTION_VAR", "ENGINE_VAR", "LaunchError", "detect_engine", "resolve", "run"]

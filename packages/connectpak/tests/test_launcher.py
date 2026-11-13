from __future__ import annotations

import importlib
import sqlite3
import sys
import tomllib
from pathlib import Path

import pytest
from connectpak.launcher import LaunchError, detect_engine, resolve
from connectpak.launcher.engines import BY_KEY, ENGINES

PACKAGES = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    ("connection", "engine"),
    [
        ("postgresql://u:p@h:5432/db", "postgres"),
        ("postgres://u:p@h/db", "postgres"),
        ("mysql://u:p@h/db", "mysql"),
        ("mariadb://u:p@h/db", "mysql"),
        ("clickhouse://u:p@h:8123/default", "clickhouse"),
        ("mssql://u:p@h/db", "sqlserver"),
        ("snowflake://u:p@acct/db/schema", "snowflake"),
        ("redshift://u:p@h:5439/db", "redshift"),
        ("databricks://token:x@h?http_path=/sql", "databricks"),
        ("mongodb+srv://u:p@cluster/db", "mongodb"),
        ("neo4j+s://u:p@cluster", "neo4j"),
        ("bolt://u:p@h:7687", "neo4j"),
        ("wss://c.cluster-x.us-east-1.neptune.amazonaws.com:8182/gremlin", "neptune"),
        ("sqlite:///tmp/x.db", "sqlite"),
        ("/data/analytics.sqlite", "sqlite"),
        ("local.db", "sqlite"),
    ],
)
def test_detects_engine_from_connection(connection: str, engine: str) -> None:
    detected = detect_engine(connection)
    assert detected is not None and detected.key == engine


@pytest.mark.parametrize(
    "connection",
    ["http://localhost:9200", "my-gcp-project", "us-east-1", "pcsk_abc", "ftp://x"],
)
def test_ambiguous_connection_is_not_guessed(connection: str) -> None:
    assert detect_engine(connection) is None
    with pytest.raises(LaunchError, match="CONNECTPAK_ENGINE"):
        resolve(connection, None, {})


def test_explicit_engine_wins_over_detection() -> None:
    engine, value = resolve("postgresql://u:p@h/db", "pgvector", {})
    assert engine.key == "pgvector" and value == "postgresql://u:p@h/db"


def test_engine_key_is_case_insensitive() -> None:
    engine, _ = resolve("http://localhost:9200", " Elasticsearch ", {})
    assert engine.key == "elasticsearch"


def test_unknown_engine_is_rejected() -> None:
    with pytest.raises(LaunchError, match="unknown engine"):
        resolve("x", "oracel", {})


@pytest.mark.parametrize(
    ("connection", "path"),
    [("sqlite:///rel/x.db", "rel/x.db"), ("sqlite:////tmp/x.db", "/tmp/x.db"),
     ("sqlite://rel.db", "rel.db")],
)
def test_sqlite_scheme_is_stripped(connection: str, path: str) -> None:
    assert resolve(connection, None, {}) == (BY_KEY["sqlite"], path)


def test_falls_back_to_engine_specific_variable() -> None:
    env = {"CONNECTPAK_MONGODB_URI": "mongodb://h/db"}
    assert resolve(None, None, env) == (BY_KEY["mongodb"], "mongodb://h/db")


def test_several_engine_variables_need_an_engine_choice() -> None:
    env = {"CONNECTPAK_MONGODB_URI": "mongodb://h", "CONNECTPAK_QDRANT_URL": "http://q"}
    with pytest.raises(LaunchError, match="several"):
        resolve(None, None, env)
    assert resolve(None, "qdrant", env) == (BY_KEY["qdrant"], "http://q")


def test_nothing_configured_is_an_error() -> None:
    with pytest.raises(LaunchError, match="no connection configured"):
        resolve(None, None, {})


@pytest.mark.parametrize("engine", ENGINES, ids=lambda e: e.key)
def test_registry_matches_engine_packages(engine) -> None:
    pyproject = tomllib.loads((PACKAGES / engine.package / "pyproject.toml").read_text())
    assert engine.cli in pyproject["project"]["scripts"]
    main = importlib.import_module(engine.module)
    assert engine.env_var in Path(main.__file__).read_text()


def test_registry_covers_every_engine_package() -> None:
    packages = {p.name for p in PACKAGES.iterdir() if (p / "pyproject.toml").exists()}
    assert packages - {"core", "connectpak"} == {e.package for e in ENGINES}


def test_meta_package_depends_on_every_engine_at_its_version() -> None:
    meta = tomllib.loads((PACKAGES / "connectpak" / "pyproject.toml").read_text())
    version = meta["project"]["version"]
    deps = set(meta["project"]["dependencies"])
    expected = {f"connectpak-{e.package}=={version}" for e in ENGINES}
    assert expected | {f"connectpak-core=={version}"} == deps


def test_launcher_serves_sqlite_end_to_end(tmp_path, monkeypatch) -> None:
    db = tmp_path / "t.db"
    sqlite3.connect(db).executescript("CREATE TABLE users (id INTEGER PRIMARY KEY);")
    served = {}

    import connectpak.sql.sqlite.__main__ as sqlite_main

    monkeypatch.setattr(sqlite_main, "serve", lambda connector: served.update(c=connector))
    monkeypatch.setenv("CONNECTPAK_CONNECTION", f"sqlite:///{db}")  # 4 slashes: absolute
    monkeypatch.delenv("CONNECTPAK_ENGINE", raising=False)
    monkeypatch.setattr(sys, "argv", ["connectpak", "--max-rows", "5"])

    from connectpak.launcher.__main__ import main

    assert main() == 0
    connector = served["c"]
    assert connector.list_tables() == [("main", "users")]
    assert connector.default_max_rows == 5
    with pytest.raises(Exception, match="read-only"):
        connector.query("DELETE FROM users")

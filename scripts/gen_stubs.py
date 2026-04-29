"""Generate the 22 stub connector packages.

Run from repo root:  python scripts/gen_stubs.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ROOT / "packages"

# (track, engine, dep_pkg, display, dialect)
# NOTE: packages with full implementations are excluded — re-running this
# script will not overwrite them. Currently full: postgres, sqlite, mysql,
# clickhouse, pgvector.
STUBS: list[tuple[str, str, str, str, str | None]] = [
    # SQL (6 stubs)
    ("sql", "sqlserver", "pymssql>=2.3", "SQL Server", "tsql"),
    ("sql", "oracle", "oracledb>=2.0", "Oracle", "oracle"),
    ("sql", "bigquery", "google-cloud-bigquery>=3.20", "BigQuery", "bigquery"),
    ("sql", "snowflake", "snowflake-connector-python>=3.7", "Snowflake", "snowflake"),
    ("sql", "redshift", "redshift-connector>=2.1", "Redshift", "redshift"),
    ("sql", "databricks", "databricks-sql-connector>=3.1", "Databricks", "databricks"),
    # NoSQL (4)
    ("nosql", "cassandra", "cassandra-driver>=3.29", "Cassandra", None),
    ("nosql", "elasticsearch", "elasticsearch>=8.13", "Elasticsearch", None),
    ("nosql", "mongodb", "pymongo>=4.7", "MongoDB", None),
    ("nosql", "dynamodb", "boto3>=1.34", "DynamoDB", None),
    # Graph (4)
    ("graph", "neo4j", "neo4j>=5.20", "Neo4j", None),
    ("graph", "neptune", "boto3>=1.34", "Neptune", None),
    ("graph", "arangodb", "python-arango>=8.0", "ArangoDB", None),
    ("graph", "memgraph", "neo4j>=5.20", "Memgraph", None),
    # Vector (5)
    ("vector", "pinecone", "pinecone-client>=4.0", "Pinecone", None),
    ("vector", "weaviate", "weaviate-client>=4.6", "Weaviate", None),
    ("vector", "qdrant", "qdrant-client>=1.9", "Qdrant", None),
    ("vector", "chroma", "chromadb>=0.5", "Chroma", None),
    ("vector", "milvus", "pymilvus>=2.4", "Milvus", None),
]

CLASS_OVERRIDES = {
    "sqlserver": "SQLServerConnector",
    "mysql": "MySQLConnector",
    "mongodb": "MongoDBConnector",
    "dynamodb": "DynamoDBConnector",
    "clickhouse": "ClickHouseConnector",
    "bigquery": "BigQueryConnector",
    "elasticsearch": "ElasticsearchConnector",
    "pgvector": "PgvectorConnector",
    "neo4j": "Neo4jConnector",
    "arangodb": "ArangoDBConnector",
}


def class_name(engine: str) -> str:
    return CLASS_OVERRIDES.get(engine, engine.capitalize() + "Connector")


PYPROJECT = """\
[project]
name = "connectpak-{track}-{engine}"
version = "0.1.0"
description = "{display} connector for connectpak (stub — not yet implemented)."
readme = "README.md"
requires-python = ">=3.11"
license = {{ text = "MIT" }}
dependencies = [
    "connectpak-core",
    "{dep}",
]

[project.scripts]
connectpak-{track}-{engine} = "connectpak.{track}.{engine}.__main__:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/connectpak"]
"""

README = """\
# connectpak-{track}-{engine}

{display} connector for connectpak.

**Status: stub — not yet implemented.** The package installs and imports, the
CLI entry point is wired up, and the connector class is registered, but every
method raises `NotImplementedError`. Contributions welcome — see
`CONTRIBUTING.md` and `packages/sql-sqlite` for the smallest reference
implementation.
"""

INIT = '''\
"""{display} connector for connectpak (stub)."""

from connectpak.{track}.{engine}.connector import {cls}

__all__ = ["{cls}"]
'''

CONNECTOR = '''\
"""{display} connector — stub.

Every method raises NotImplementedError. Implement against the contract
defined in `connectpak.core.base.BaseConnector` and keep the safety
contract intact: parser guard + engine-level read-only + statement timeout
+ row cap.
"""

from __future__ import annotations

from connectpak.core.base import BaseConnector, QueryResult, TableSchema


class {cls}(BaseConnector):
    name = "{engine}"
    dialect = {dialect_repr}

    def list_schemas(self) -> list[str]:
        raise NotImplementedError("{display} connector is not yet implemented")

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        raise NotImplementedError("{display} connector is not yet implemented")

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        raise NotImplementedError("{display} connector is not yet implemented")

    def sample_table(
        self, name: str, schema: str | None = None, limit: int = 10
    ) -> QueryResult:
        raise NotImplementedError("{display} connector is not yet implemented")

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        raise NotImplementedError("{display} connector is not yet implemented")

    def explain(self, sql: str) -> str:
        raise NotImplementedError("{display} connector is not yet implemented")

    def close(self) -> None:
        return None
'''

MAIN = '''\
"""CLI entry point for the {display} connector (stub)."""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "connectpak-{track}-{engine}: stub — not yet implemented",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
'''


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def main() -> None:
    for track, engine, dep, display, dialect in STUBS:
        cls = class_name(engine)
        pkg = PACKAGES / f"{track}-{engine}"
        src = pkg / "src" / "connectpak" / track / engine
        dialect_repr = repr(dialect) if dialect is not None else "None"

        write(
            pkg / "pyproject.toml",
            PYPROJECT.format(track=track, engine=engine, display=display, dep=dep),
        )
        write(pkg / "README.md", README.format(track=track, engine=engine, display=display))
        write(
            src / "__init__.py",
            INIT.format(track=track, engine=engine, display=display, cls=cls),
        )
        write(
            src / "connector.py",
            CONNECTOR.format(
                engine=engine, display=display, cls=cls, dialect_repr=dialect_repr
            ),
        )
        write(src / "__main__.py", MAIN.format(track=track, engine=engine, display=display))

    print(f"Generated {len(STUBS)} stub packages.")


if __name__ == "__main__":
    main()

"""Scaffold CLI / README / offline tests for newly-implemented connectors.

For each (track, engine, class_name, env_var, display, dialect) tuple this
writes:
  - packages/{track}-{engine}/README.md
  - packages/{track}-{engine}/src/connectpak/{track}/{engine}/__main__.py
  - packages/{track}-{engine}/tests/test_connector.py

The connector.py itself is hand-written for each engine — this script does
NOT touch it.

Run from repo root:  python scripts/scaffold_impls.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ROOT / "packages"


# (track, engine, class_name, env_var, display, dialect_for_sqlglot, sample_write_sql)
IMPLS: list[tuple[str, str, str, str, str, str | None, str]] = [
    ("sql", "oracle", "OracleConnector", "CONNECTPAK_ORACLE_DSN",
     "Oracle", "oracle", "DELETE FROM users"),
    ("sql", "bigquery", "BigQueryConnector", "CONNECTPAK_BIGQUERY_PROJECT",
     "BigQuery", "bigquery", "DELETE FROM dataset.users WHERE TRUE"),
    ("sql", "snowflake", "SnowflakeConnector", "CONNECTPAK_SNOWFLAKE_DSN",
     "Snowflake", "snowflake", "DELETE FROM users"),
    ("sql", "redshift", "RedshiftConnector", "CONNECTPAK_REDSHIFT_DSN",
     "Redshift", "redshift", "DELETE FROM users"),
    ("sql", "databricks", "DatabricksConnector", "CONNECTPAK_DATABRICKS_DSN",
     "Databricks", "databricks", "DELETE FROM users"),
    ("nosql", "mongodb", "MongoDBConnector", "CONNECTPAK_MONGODB_URI",
     "MongoDB", None, ""),
    ("nosql", "dynamodb", "DynamoDBConnector", "CONNECTPAK_DYNAMODB_REGION",
     "DynamoDB", None, ""),
    ("nosql", "elasticsearch", "ElasticsearchConnector", "CONNECTPAK_ELASTICSEARCH_URL",
     "Elasticsearch", None, ""),
    ("nosql", "cassandra", "CassandraConnector", "CONNECTPAK_CASSANDRA_HOSTS",
     "Cassandra", None, ""),
    ("graph", "neo4j", "Neo4jConnector", "CONNECTPAK_NEO4J_URI",
     "Neo4j", None, ""),
    ("graph", "memgraph", "MemgraphConnector", "CONNECTPAK_MEMGRAPH_URI",
     "Memgraph", None, ""),
    ("graph", "arangodb", "ArangoDBConnector", "CONNECTPAK_ARANGODB_URL",
     "ArangoDB", None, ""),
    ("graph", "neptune", "NeptuneConnector", "CONNECTPAK_NEPTUNE_URL",
     "Neptune", None, ""),
    ("vector", "pinecone", "PineconeConnector", "CONNECTPAK_PINECONE_API_KEY",
     "Pinecone", None, ""),
    ("vector", "weaviate", "WeaviateConnector", "CONNECTPAK_WEAVIATE_URL",
     "Weaviate", None, ""),
    ("vector", "qdrant", "QdrantConnector", "CONNECTPAK_QDRANT_URL",
     "Qdrant", None, ""),
    ("vector", "chroma", "ChromaConnector", "CONNECTPAK_CHROMA_URL",
     "Chroma", None, ""),
    ("vector", "milvus", "MilvusConnector", "CONNECTPAK_MILVUS_URI",
     "Milvus", None, ""),
]


CLI_TEMPLATE = '''\
"""CLI entry point for the {display} connector."""

from __future__ import annotations

import argparse
import os
import sys

from connectpak.core.server import serve
from connectpak.{track}.{engine}.connector import {cls}


def main() -> int:
    parser = argparse.ArgumentParser(prog="connectpak-{track}-{engine}")
    parser.add_argument(
        "--config",
        default=os.environ.get("{env_var}"),
        help="{display} connection config (default: ${env_var}). "
             "See the connector's docstring for accepted formats.",
    )
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument("--statement-timeout-ms", type=int, default=30_000)
    parser.add_argument("--max-rows", type=int, default=1000)
    args = parser.parse_args()
    if not args.config:
        print(
            "error: --config is required (or set ${env_var})",
            file=sys.stderr,
        )
        return 2
    serve({cls}(
        config=args.config,
        allow_write=args.allow_write,
        statement_timeout_ms=args.statement_timeout_ms,
        default_max_rows=args.max_rows,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


README_TEMPLATE = """\
# connectpak-{track}-{engine}

{display} connector for connectpak.

## Quick start

```bash
uv sync
export {env_var}="..."
uv run connectpak-{track}-{engine}
```

See the connector module docstring for the accepted config / DSN format and
for any engine-specific safety notes (engine-level read-only mode, statement
timeout mechanism, query language for the `query` tool).
"""


SQL_TEST_TEMPLATE = '''\
"""Offline tests for {cls}. Live engine tests run separately."""

from __future__ import annotations

import pytest

from connectpak.core.guard import WriteOperationError
from connectpak.{track}.{engine}.connector import {cls}


def test_class_metadata() -> None:
    c = {cls}.__new__({cls})
    assert c.name == "{engine}"


def test_query_guard_rejects_writes_before_connecting() -> None:
    c = {cls}.__new__({cls})
    c.allow_write = False
    c.dialect = {dialect_repr}
    c.statement_timeout_ms = 1
    c.default_max_rows = 1
    with pytest.raises(WriteOperationError):
        c.query({sample_write_sql!r})
'''


NONSQL_TEST_TEMPLATE = '''\
"""Offline tests for {cls}. Live engine tests run separately."""

from __future__ import annotations

from connectpak.{track}.{engine}.connector import {cls}


def test_class_metadata() -> None:
    c = {cls}.__new__({cls})
    assert c.name == "{engine}"
'''


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def main() -> None:
    written = 0
    for track, engine, cls, env_var, display, dialect, sample_write in IMPLS:
        pkg = PACKAGES / f"{track}-{engine}"
        src = pkg / "src" / "connectpak" / track / engine

        write(pkg / "README.md",
              README_TEMPLATE.format(track=track, engine=engine,
                                     display=display, env_var=env_var))
        write(src / "__main__.py",
              CLI_TEMPLATE.format(track=track, engine=engine, display=display,
                                  cls=cls, env_var=env_var))
        if dialect:
            write(pkg / "tests" / "test_connector.py",
                  SQL_TEST_TEMPLATE.format(track=track, engine=engine, cls=cls,
                                           dialect_repr=repr(dialect),
                                           sample_write_sql=sample_write))
        else:
            write(pkg / "tests" / "test_connector.py",
                  NONSQL_TEST_TEMPLATE.format(track=track, engine=engine, cls=cls))
        written += 4

    print(f"Scaffolded {written} files across {len(IMPLS)} packages.")


if __name__ == "__main__":
    main()

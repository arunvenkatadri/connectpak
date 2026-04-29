"""Offline tests for PgvectorConnector.

PgvectorConnector inherits from PostgresConnector and only overrides
`_fetch_columns`. Live engine tests require a Postgres instance with the
pgvector extension installed. These tests confirm the inheritance chain and
that the parser guard fires before any connection attempt.
"""

from __future__ import annotations

import pytest

from connectpak.core.guard import WriteOperationError
from connectpak.sql.postgres.connector import PostgresConnector
from connectpak.vector.pgvector.connector import PgvectorConnector


def test_pgvector_is_a_postgres_connector() -> None:
    assert issubclass(PgvectorConnector, PostgresConnector)


def test_pgvector_reports_its_own_name_and_postgres_dialect() -> None:
    c = PgvectorConnector("postgresql://nobody:nope@127.0.0.1:1/no")
    assert c.name == "pgvector"
    assert c.dialect == "postgres"


def test_query_guard_rejects_writes_before_connecting() -> None:
    c = PgvectorConnector("postgresql://nobody:nope@127.0.0.1:1/no")
    with pytest.raises(WriteOperationError):
        c.query("DELETE FROM embeddings")


def test_query_guard_rejects_cte_wrapped_delete() -> None:
    c = PgvectorConnector("postgresql://nobody:nope@127.0.0.1:1/no")
    with pytest.raises(WriteOperationError):
        c.query(
            "WITH gone AS (DELETE FROM embeddings RETURNING id) SELECT * FROM gone"
        )

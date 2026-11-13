"""Live tests against a real Postgres.

Set CONNECTPAK_TEST_POSTGRES_DSN to a superuser DSN to run them (CI starts a
Postgres service and sets it). They create and drop their own schemas.
"""

from __future__ import annotations

import os

import pytest

psycopg = pytest.importorskip("psycopg")

from connectpak.core.guard import WriteOperationError  # noqa: E402
from connectpak.sql.postgres.connector import PostgresConnector  # noqa: E402

DSN = os.environ.get("CONNECTPAK_TEST_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="CONNECTPAK_TEST_POSTGRES_DSN not set")

SCHEMAS = ("cpk_shop", "pgsales")  # "pgsales" must not be mistaken for a pg_ schema


@pytest.fixture(scope="module")
def connector():
    with psycopg.connect(DSN, autocommit=True) as admin:
        for s in SCHEMAS:
            admin.execute(f"DROP SCHEMA IF EXISTS {s} CASCADE")
        admin.execute(
            """
            CREATE SCHEMA cpk_shop;
            CREATE TABLE cpk_shop.customers (
                id serial PRIMARY KEY, name text NOT NULL, region text
            );
            CREATE TABLE cpk_shop.orders (
                id serial PRIMARY KEY,
                customer_id int NOT NULL REFERENCES cpk_shop.customers(id),
                total numeric(10, 2)
            );
            CREATE INDEX orders_customer_idx ON cpk_shop.orders (customer_id);
            CREATE VIEW cpk_shop.big_orders AS SELECT * FROM cpk_shop.orders WHERE total > 50;
            INSERT INTO cpk_shop.customers (name, region) VALUES ('Ada', 'EU'), ('Grace', 'US');
            INSERT INTO cpk_shop.orders (customer_id, total) VALUES (1, 10), (1, 32.5), (2, 99);
            CREATE SCHEMA pgsales;
            CREATE TABLE pgsales.leads (id int PRIMARY KEY);
            """
        )
    c = PostgresConnector(DSN, default_max_rows=2)
    yield c
    c.close()
    with psycopg.connect(DSN, autocommit=True) as admin:
        for s in SCHEMAS:
            admin.execute(f"DROP SCHEMA IF EXISTS {s} CASCADE")


def test_list_schemas_hides_system_schemas_only(connector) -> None:
    schemas = connector.list_schemas()
    assert {"cpk_shop", "pgsales", "public"} <= set(schemas)
    assert not {"pg_catalog", "information_schema", "pg_toast"} & set(schemas)


def test_list_tables_without_schema(connector) -> None:
    tables = connector.list_tables()
    assert ("cpk_shop", "customers") in tables
    assert ("cpk_shop", "big_orders") in tables  # views included
    assert ("pgsales", "leads") in tables
    assert not any(s.startswith("pg_") or s == "information_schema" for s, _ in tables)


def test_list_tables_with_schema(connector) -> None:
    assert connector.list_tables("cpk_shop") == [
        ("cpk_shop", "big_orders"), ("cpk_shop", "customers"), ("cpk_shop", "orders"),
    ]


def test_describe_table(connector) -> None:
    t = connector.describe_table("orders", schema="cpk_shop")
    assert [c.name for c in t.columns] == ["id", "customer_id", "total"]
    assert t.primary_key == ["id"]
    fk = t.foreign_keys[0]
    assert (fk.columns, fk.referenced_schema, fk.referenced_table, fk.referenced_columns) == (
        ["customer_id"], "cpk_shop", "customers", ["id"]
    )
    idx = {i.name: i for i in t.indexes}
    assert idx["orders_customer_idx"].columns == ["customer_id"]


def test_sample_and_query(connector) -> None:
    sample = connector.sample_table("customers", schema="cpk_shop", limit=5)
    assert len(sample.rows) == 2
    result = connector.query(
        "SELECT c.name, sum(o.total) AS spent FROM cpk_shop.orders o "
        "JOIN cpk_shop.customers c ON c.id = o.customer_id GROUP BY c.name ORDER BY spent DESC"
    )
    assert result.rows[0][0] == "Grace"


def test_row_cap_marks_truncation(connector) -> None:
    result = connector.query("SELECT * FROM cpk_shop.orders")
    assert len(result.rows) == 2 and result.truncated


def test_like_with_percent_in_user_query(connector) -> None:
    result = connector.query("SELECT name FROM cpk_shop.customers WHERE name LIKE 'A%'")
    assert [list(r) for r in result.rows] == [["Ada"]]


def test_explain(connector) -> None:
    assert "Scan" in connector.explain("SELECT * FROM cpk_shop.orders WHERE customer_id = 1")


def test_writes_rejected_by_guard(connector) -> None:
    with pytest.raises(WriteOperationError):
        connector.query("UPDATE cpk_shop.customers SET region = 'X'")


def test_engine_rejects_writes_the_guard_cannot_see(connector) -> None:
    # A volatile function call parses as a plain SELECT, so only the engine's
    # read-only transaction stops it.
    with pytest.raises(Exception, match="read-only"):
        connector.query("SELECT nextval('cpk_shop.customers_id_seq')")

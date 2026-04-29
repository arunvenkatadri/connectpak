"""Snowflake connector using snowflake-connector-python.

Config: a query-string DSN, e.g.
    snowflake://user:pass@account/db/schema?warehouse=WH&role=READONLY

Engine-level read-only: STATEMENT_TIMEOUT_IN_SECONDS at the session, plus
parser guard. For real production deployments use a role that only has
USAGE / SELECT privileges.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import snowflake.connector

from connectpak.core.base import (
    BaseConnector,
    Column,
    ForeignKey,
    Index,
    QueryResult,
    TableSchema,
)
from connectpak.core.guard import assert_read_only


def _parse_config(config: str) -> dict[str, Any]:
    p = urlparse(config)
    if p.scheme != "snowflake":
        raise ValueError("snowflake config must be a snowflake://... URL")
    parts = (p.path or "").lstrip("/").split("/")
    database = parts[0] if parts and parts[0] else None
    schema = parts[1] if len(parts) > 1 and parts[1] else None
    qs = {k: v[0] for k, v in parse_qs(p.query).items()}
    out: dict[str, Any] = {
        "user": unquote(p.username) if p.username else None,
        "password": unquote(p.password) if p.password else None,
        "account": p.hostname,
        "database": database,
        "schema": schema,
    }
    for key in ("warehouse", "role"):
        if key in qs:
            out[key] = qs[key]
    return out


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class SnowflakeConnector(BaseConnector):
    name = "snowflake"
    dialect = "snowflake"

    def __init__(
        self,
        config: str,
        *,
        allow_write: bool = False,
        statement_timeout_ms: int = 30_000,
        default_max_rows: int = 1000,
    ):
        self.config = config
        self.allow_write = allow_write
        self.statement_timeout_ms = statement_timeout_ms
        self.default_max_rows = default_max_rows
        self._conn: Any = None

    def _connection(self) -> Any:
        if self._conn is not None:
            return self._conn
        params = _parse_config(self.config)
        conn = snowflake.connector.connect(autocommit=True, **params)
        with conn.cursor() as cur:
            cur.execute(
                f"ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS = "
                f"{max(1, int(self.statement_timeout_ms / 1000))}"
            )
        self._conn = conn
        return conn

    def list_schemas(self) -> list[str]:
        sql = (
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name NOT IN ('INFORMATION_SCHEMA') ORDER BY schema_name"
        )
        with self._connection().cursor() as cur:
            cur.execute(sql)
            return [r[0] for r in cur.fetchall()]

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        if schema is None:
            sql = (
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_type IN ('BASE TABLE','VIEW') "
                "AND table_schema <> 'INFORMATION_SCHEMA' "
                "ORDER BY table_schema, table_name"
            )
            params: tuple = ()
        else:
            sql = (
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_type IN ('BASE TABLE','VIEW') AND table_schema = %s "
                "ORDER BY table_name"
            )
            params = (schema.upper(),)
        with self._connection().cursor() as cur:
            cur.execute(sql, params)
            return [(r[0], r[1]) for r in cur.fetchall()]

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        schema_u = (schema or "PUBLIC").upper()
        name_u = name.upper()
        cols = self._fetch_columns(schema_u, name_u)
        pk = self._fetch_primary_key(schema_u, name_u)
        fks = self._fetch_foreign_keys(schema_u, name_u)
        pk_set = set(pk)
        for c in cols:
            if c.name in pk_set:
                c.is_primary_key = True
        return TableSchema(schema=schema_u, name=name_u, columns=cols,
                           primary_key=pk, foreign_keys=fks, indexes=[])

    def _fetch_columns(self, schema: str, table: str) -> list[Column]:
        sql = (
            "SELECT column_name, data_type, is_nullable, column_default, comment "
            "FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position"
        )
        with self._connection().cursor() as cur:
            cur.execute(sql, (schema, table))
            return [
                Column(name=r[0], type=r[1], nullable=(r[2] == "YES"),
                       default=r[3], comment=r[4])
                for r in cur.fetchall()
            ]

    def _fetch_primary_key(self, schema: str, table: str) -> list[str]:
        with self._connection().cursor() as cur:
            cur.execute(f'SHOW PRIMARY KEYS IN TABLE "{schema}"."{table}"')
            rows = cur.fetchall()
            cols = [d[0] for d in (cur.description or [])]
        col_idx = {c.lower(): i for i, c in enumerate(cols)}
        if "column_name" not in col_idx:
            return []
        return [r[col_idx["column_name"]] for r in rows]

    def _fetch_foreign_keys(self, schema: str, table: str) -> list[ForeignKey]:
        with self._connection().cursor() as cur:
            cur.execute(f'SHOW IMPORTED KEYS IN TABLE "{schema}"."{table}"')
            rows = cur.fetchall()
            cols = [d[0] for d in (cur.description or [])]
        idx = {c.lower(): i for i, c in enumerate(cols)}
        if "fk_name" not in idx:
            return []
        grouped: dict[str, dict[str, Any]] = {}
        for r in rows:
            cname = r[idx["fk_name"]]
            entry = grouped.setdefault(
                cname, {"name": cname, "columns": [],
                        "ref_schema": r[idx.get("pk_schema_name", -1)] if idx.get("pk_schema_name", -1) >= 0 else None,
                        "ref_table": r[idx["pk_table_name"]],
                        "ref_columns": []},
            )
            entry["columns"].append(r[idx["fk_column_name"]])
            entry["ref_columns"].append(r[idx["pk_column_name"]])
        return [
            ForeignKey(columns=g["columns"], referenced_schema=g["ref_schema"],
                       referenced_table=g["ref_table"], referenced_columns=g["ref_columns"],
                       name=g["name"])
            for g in grouped.values()
        ]

    def sample_table(self, name: str, schema: str | None = None, limit: int = 10) -> QueryResult:
        ident = _quote_ident(name.upper())
        if schema:
            ident = f"{_quote_ident(schema.upper())}.{ident}"
        return self._run(f"SELECT * FROM {ident} LIMIT {int(limit)}", max_rows=limit)

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        if not self.allow_write:
            assert_read_only(sql, dialect=self.dialect)
        return self._run(sql, max_rows=max_rows)

    def explain(self, sql: str) -> str:
        with self._connection().cursor() as cur:
            cur.execute("EXPLAIN " + sql)
            cols = [d[0] for d in (cur.description or [])]
            rows = cur.fetchall()
        lines = [" | ".join(cols)]
        lines.extend(" | ".join(str(c) for c in r) for r in rows)
        return "\n".join(lines)

    def _run(self, sql: str, max_rows: int | None = None) -> QueryResult:
        cap = max_rows if max_rows is not None else self.default_max_rows
        start = time.perf_counter()
        with self._connection().cursor() as cur:
            cur.execute(sql)
            cols = [d[0] for d in (cur.description or [])]
            rows = cur.fetchmany(cap + 1)
        elapsed = (time.perf_counter() - start) * 1000.0
        truncated = len(rows) > cap
        if truncated:
            rows = rows[:cap]
        return QueryResult(columns=cols, rows=[list(r) for r in rows],
                           row_count=len(rows), truncated=truncated, elapsed_ms=elapsed)

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None

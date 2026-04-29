"""Amazon Redshift connector using redshift-connector.

Config: a Postgres-style DSN, e.g.
    redshift://user:pass@host:5439/db
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import unquote, urlparse

import redshift_connector

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
    if p.scheme not in ("redshift", "postgres", "postgresql", ""):
        raise ValueError(f"unsupported Redshift DSN scheme: {p.scheme!r}")
    return {
        "host": p.hostname,
        "port": p.port or 5439,
        "user": unquote(p.username) if p.username else None,
        "password": unquote(p.password) if p.password else None,
        "database": p.path.lstrip("/") or None,
    }


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class RedshiftConnector(BaseConnector):
    name = "redshift"
    dialect = "redshift"

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
        conn = redshift_connector.connect(**params)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = {int(self.statement_timeout_ms)}")
            if not self.allow_write:
                cur.execute("SET default_transaction_read_only = on")
        self._conn = conn
        return conn

    def list_schemas(self) -> list[str]:
        sql = (
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name NOT IN ('pg_catalog','information_schema','pg_toast') "
            "AND schema_name NOT LIKE 'pg_%' ORDER BY schema_name"
        )
        with self._connection().cursor() as cur:
            cur.execute(sql)
            return [r[0] for r in cur.fetchall()]

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        if schema is None:
            sql = (
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_type IN ('BASE TABLE','VIEW') "
                "AND table_schema NOT IN ('pg_catalog','information_schema') "
                "ORDER BY table_schema, table_name"
            )
            params: tuple = ()
        else:
            sql = (
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_type IN ('BASE TABLE','VIEW') AND table_schema = %s "
                "ORDER BY table_name"
            )
            params = (schema,)
        with self._connection().cursor() as cur:
            cur.execute(sql, params)
            return [(r[0], r[1]) for r in cur.fetchall()]

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        schema = schema or "public"
        cols = self._fetch_columns(schema, name)
        pk = self._fetch_primary_key(schema, name)
        fks = self._fetch_foreign_keys(schema, name)
        pk_set = set(pk)
        for c in cols:
            if c.name in pk_set:
                c.is_primary_key = True
        return TableSchema(schema=schema, name=name, columns=cols,
                           primary_key=pk, foreign_keys=fks, indexes=[])

    def _fetch_columns(self, schema: str, table: str) -> list[Column]:
        sql = (
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_schema = %s AND table_name = %s ORDER BY ordinal_position"
        )
        with self._connection().cursor() as cur:
            cur.execute(sql, (schema, table))
            return [
                Column(name=r[0], type=r[1], nullable=(r[2] == "YES"), default=r[3])
                for r in cur.fetchall()
            ]

    def _fetch_primary_key(self, schema: str, table: str) -> list[str]:
        sql = (
            "SELECT kcu.column_name "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name "
            "WHERE tc.constraint_type = 'PRIMARY KEY' "
            "AND tc.table_schema = %s AND tc.table_name = %s "
            "ORDER BY kcu.ordinal_position"
        )
        with self._connection().cursor() as cur:
            cur.execute(sql, (schema, table))
            return [r[0] for r in cur.fetchall()]

    def _fetch_foreign_keys(self, schema: str, table: str) -> list[ForeignKey]:
        sql = (
            "SELECT tc.constraint_name, kcu.column_name, "
            "       ccu.table_schema, ccu.table_name, ccu.column_name, kcu.ordinal_position "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "  ON tc.constraint_name = kcu.constraint_name "
            "JOIN information_schema.constraint_column_usage ccu "
            "  ON tc.constraint_name = ccu.constraint_name "
            "WHERE tc.constraint_type = 'FOREIGN KEY' "
            "AND tc.table_schema = %s AND tc.table_name = %s "
            "ORDER BY tc.constraint_name, kcu.ordinal_position"
        )
        with self._connection().cursor() as cur:
            cur.execute(sql, (schema, table))
            rows = cur.fetchall()
        grouped: dict[str, dict[str, Any]] = {}
        for cname, col, ref_schema, ref_table, ref_col, _ord in rows:
            entry = grouped.setdefault(
                cname, {"name": cname, "columns": [], "ref_schema": ref_schema,
                        "ref_table": ref_table, "ref_columns": []},
            )
            entry["columns"].append(col)
            entry["ref_columns"].append(ref_col)
        return [
            ForeignKey(columns=g["columns"], referenced_schema=g["ref_schema"],
                       referenced_table=g["ref_table"], referenced_columns=g["ref_columns"],
                       name=g["name"])
            for g in grouped.values()
        ]

    def sample_table(self, name: str, schema: str | None = None, limit: int = 10) -> QueryResult:
        ident = _quote_ident(name)
        if schema:
            ident = f"{_quote_ident(schema)}.{ident}"
        return self._run(f"SELECT * FROM {ident} LIMIT {int(limit)}", max_rows=limit)

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        if not self.allow_write:
            assert_read_only(sql, dialect=self.dialect)
        return self._run(sql, max_rows=max_rows)

    def explain(self, sql: str) -> str:
        with self._connection().cursor() as cur:
            cur.execute("EXPLAIN " + sql)
            return "\n".join(str(r[0]) for r in cur.fetchall())

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

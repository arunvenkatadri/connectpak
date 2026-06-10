"""Databricks SQL connector using databricks-sql-connector.

Config: a query-string DSN, e.g.
    databricks://token:dapi-xxxxx@host.cloud.databricks.com?http_path=/sql/1.0/...
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from connectpak.core.base import (
    BaseConnector,
    Column,
    QueryResult,
    TableSchema,
)
from connectpak.core.guard import assert_read_only

from databricks import sql as dbsql


def _parse_config(config: str) -> dict[str, Any]:
    p = urlparse(config)
    if p.scheme != "databricks":
        raise ValueError("databricks config must be a databricks://... URL")
    qs = {k: v[0] for k, v in parse_qs(p.query).items()}
    if "http_path" not in qs:
        raise ValueError("databricks DSN must include ?http_path=/sql/...")
    if not p.password:
        raise ValueError("databricks DSN must include token in user:password slot")
    return {
        "server_hostname": p.hostname,
        "http_path": qs["http_path"],
        "access_token": unquote(p.password),
        "_catalog": qs.get("catalog"),
        "_schema": qs.get("schema"),
    }


def _quote_ident(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


class DatabricksConnector(BaseConnector):
    name = "databricks"
    dialect = "databricks"

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
        self._catalog: str | None = None

    def _connection(self) -> Any:
        if self._conn is not None:
            return self._conn
        params = _parse_config(self.config)
        self._catalog = params.pop("_catalog")
        default_schema = params.pop("_schema")
        self._conn = dbsql.connect(**params)
        if self._catalog:
            with self._conn.cursor() as cur:
                cur.execute(f"USE CATALOG {_quote_ident(self._catalog)}")
        if default_schema:
            with self._conn.cursor() as cur:
                cur.execute(f"USE SCHEMA {_quote_ident(default_schema)}")
        return self._conn

    def list_schemas(self) -> list[str]:
        sql = (
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name <> 'information_schema' ORDER BY schema_name"
        )
        with self._connection().cursor() as cur:
            cur.execute(sql)
            return [r[0] for r in cur.fetchall()]

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        if schema is None:
            sql = (
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_schema <> 'information_schema' "
                "ORDER BY table_schema, table_name"
            )
            params: tuple = ()
        else:
            sql = (
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_schema = %(s)s ORDER BY table_name"
            )
            params = ({"s": schema},)
        with self._connection().cursor() as cur:
            if params:
                cur.execute(sql, params[0])
            else:
                cur.execute(sql)
            return [(r[0], r[1]) for r in cur.fetchall()]

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        schema = schema or "default"
        sql = (
            "SELECT column_name, data_type, is_nullable, column_default, comment "
            "FROM information_schema.columns "
            "WHERE table_schema = %(s)s AND table_name = %(t)s "
            "ORDER BY ordinal_position"
        )
        with self._connection().cursor() as cur:
            cur.execute(sql, {"s": schema, "t": name})
            cols = [
                Column(name=r[0], type=r[1], nullable=(r[2] == "YES"),
                       default=r[3], comment=r[4])
                for r in cur.fetchall()
            ]
        return TableSchema(schema=schema, name=name, columns=cols,
                           primary_key=[], foreign_keys=[], indexes=[])

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

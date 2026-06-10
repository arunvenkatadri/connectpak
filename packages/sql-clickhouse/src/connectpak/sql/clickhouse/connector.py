"""ClickHouse connector using clickhouse-connect (HTTP)."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import unquote, urlparse

import clickhouse_connect
from connectpak.core.base import (
    BaseConnector,
    Column,
    Index,
    QueryResult,
    TableSchema,
)
from connectpak.core.guard import assert_read_only

_SYSTEM_DBS = ("system", "INFORMATION_SCHEMA", "information_schema")


def _parse_dsn(dsn: str) -> dict[str, Any]:
    p = urlparse(dsn)
    if p.scheme not in ("clickhouse", "clickhouse+http", "http", "https", ""):
        raise ValueError(f"unsupported ClickHouse DSN scheme: {p.scheme!r}")
    secure = p.scheme == "https"
    return {
        "host": p.hostname or "localhost",
        "port": p.port or (8443 if secure else 8123),
        "username": unquote(p.username) if p.username else "default",
        "password": unquote(p.password) if p.password else "",
        "database": p.path.lstrip("/") or "default",
        "secure": secure,
    }


def _quote_ident(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


def _is_nullable(type_str: str) -> bool:
    return type_str.startswith("Nullable(")


class ClickHouseConnector(BaseConnector):
    name = "clickhouse"
    dialect = "clickhouse"

    def __init__(
        self,
        dsn: str,
        *,
        allow_write: bool = False,
        statement_timeout_ms: int = 30_000,
        default_max_rows: int = 1000,
    ):
        self.dsn = dsn
        self.allow_write = allow_write
        self.statement_timeout_ms = statement_timeout_ms
        self.default_max_rows = default_max_rows
        self._client: Any = None

    def _connection(self) -> Any:
        if self._client is not None:
            return self._client
        params = _parse_dsn(self.dsn)
        settings: dict[str, Any] = {
            "max_execution_time": max(1, int(self.statement_timeout_ms / 1000)),
        }
        if not self.allow_write:
            settings["readonly"] = 1
        self._client = clickhouse_connect.get_client(settings=settings, **params)
        return self._client

    def list_schemas(self) -> list[str]:
        sql = (
            "SELECT name FROM system.databases "
            "WHERE name NOT IN {names:Array(String)} ORDER BY name"
        )
        result = self._connection().query(sql, parameters={"names": list(_SYSTEM_DBS)})
        return [r[0] for r in result.result_rows]

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        if schema is None:
            sql = (
                "SELECT database, name FROM system.tables "
                "WHERE database NOT IN {names:Array(String)} "
                "ORDER BY database, name"
            )
            params = {"names": list(_SYSTEM_DBS)}
        else:
            sql = (
                "SELECT database, name FROM system.tables "
                "WHERE database = {db:String} ORDER BY name"
            )
            params = {"db": schema}
        result = self._connection().query(sql, parameters=params)
        return [(r[0], r[1]) for r in result.result_rows]

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        schema = schema or self._current_database()
        cols = self._fetch_columns(schema, name)
        pk = [c.name for c in cols if c.is_primary_key]
        indexes = self._fetch_indexes(schema, name)
        comment = self._fetch_table_comment(schema, name)
        return TableSchema(
            schema=schema,
            name=name,
            columns=cols,
            primary_key=pk,
            foreign_keys=[],
            indexes=indexes,
            comment=comment,
        )

    def _current_database(self) -> str:
        result = self._connection().query("SELECT currentDatabase()")
        return result.result_rows[0][0]

    def _fetch_columns(self, schema: str, table: str) -> list[Column]:
        sql = """
            SELECT name, type, default_kind, default_expression, comment, is_in_primary_key
            FROM system.columns
            WHERE database = {db:String} AND table = {tbl:String}
            ORDER BY position
        """
        result = self._connection().query(sql, parameters={"db": schema, "tbl": table})
        cols: list[Column] = []
        for cname, ctype, dflt_kind, dflt_expr, comment, is_pk in result.result_rows:
            default = dflt_expr if dflt_kind in ("DEFAULT", "MATERIALIZED", "ALIAS") and dflt_expr else None
            cols.append(
                Column(
                    name=cname,
                    type=ctype,
                    nullable=_is_nullable(ctype),
                    default=default,
                    is_primary_key=bool(is_pk),
                    comment=comment or None,
                )
            )
        return cols

    def _fetch_indexes(self, schema: str, table: str) -> list[Index]:
        sql = """
            SELECT name, expr
            FROM system.data_skipping_indices
            WHERE database = {db:String} AND table = {tbl:String}
            ORDER BY name
        """
        result = self._connection().query(sql, parameters={"db": schema, "tbl": table})
        return [
            Index(name=r[0], columns=[r[1]], unique=False)
            for r in result.result_rows
        ]

    def _fetch_table_comment(self, schema: str, table: str) -> str | None:
        sql = (
            "SELECT comment FROM system.tables "
            "WHERE database = {db:String} AND name = {tbl:String}"
        )
        result = self._connection().query(sql, parameters={"db": schema, "tbl": table})
        if not result.result_rows:
            return None
        c = result.result_rows[0][0]
        return c or None

    def sample_table(
        self, name: str, schema: str | None = None, limit: int = 10
    ) -> QueryResult:
        ident = _quote_ident(name)
        if schema:
            ident = f"{_quote_ident(schema)}.{ident}"
        return self._run(f"SELECT * FROM {ident} LIMIT {int(limit)}", max_rows=limit)

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        if not self.allow_write:
            assert_read_only(sql, dialect=self.dialect)
        return self._run(sql, max_rows=max_rows)

    def explain(self, sql: str) -> str:
        result = self._connection().query("EXPLAIN " + sql)
        return "\n".join(str(r[0]) for r in result.result_rows)

    def _run(self, sql: str, max_rows: int | None = None) -> QueryResult:
        cap = max_rows if max_rows is not None else self.default_max_rows
        capped_sql = f"SELECT * FROM ({sql}) LIMIT {cap + 1}"
        start = time.perf_counter()
        result = self._connection().query(capped_sql)
        elapsed = (time.perf_counter() - start) * 1000.0
        rows = [list(r) for r in result.result_rows]
        truncated = len(rows) > cap
        if truncated:
            rows = rows[:cap]
        return QueryResult(
            columns=list(result.column_names),
            rows=rows,
            row_count=len(rows),
            truncated=truncated,
            elapsed_ms=elapsed,
        )

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
        self._client = None

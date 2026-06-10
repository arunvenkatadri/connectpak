"""SQL Server connector using pymssql."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import unquote, urlparse

import pymssql
from connectpak.core.base import (
    BaseConnector,
    Column,
    ForeignKey,
    Index,
    QueryResult,
    TableSchema,
)
from connectpak.core.guard import assert_read_only


def _parse_dsn(dsn: str) -> dict[str, Any]:
    p = urlparse(dsn)
    if p.scheme not in ("mssql", "sqlserver", ""):
        raise ValueError(f"unsupported SQL Server DSN scheme: {p.scheme!r}")
    return {
        "server": p.hostname or "localhost",
        "port": p.port or 1433,
        "user": unquote(p.username) if p.username else None,
        "password": unquote(p.password) if p.password else None,
        "database": p.path.lstrip("/") or None,
    }


def _quote_ident(name: str) -> str:
    return "[" + name.replace("]", "]]") + "]"


class SQLServerConnector(BaseConnector):
    name = "sqlserver"
    dialect = "tsql"

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
        self._conn: Any = None

    def _connection(self) -> Any:
        if self._conn is not None:
            return self._conn
        params = _parse_dsn(self.dsn)
        timeout_s = max(1, int(self.statement_timeout_ms / 1000))
        self._conn = pymssql.connect(
            autocommit=True, timeout=timeout_s, login_timeout=timeout_s, **params
        )
        return self._conn

    def list_schemas(self) -> list[str]:
        sql = (
            "SELECT name FROM sys.schemas "
            "WHERE name NOT IN ('sys','INFORMATION_SCHEMA','guest') "
            "AND name NOT LIKE 'db_%' ORDER BY name"
        )
        with self._connection().cursor() as cur:
            cur.execute(sql)
            return [r[0] for r in cur.fetchall()]

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        if schema is None:
            sql = (
                "SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE IN ('BASE TABLE','VIEW') "
                "ORDER BY TABLE_SCHEMA, TABLE_NAME"
            )
            params: tuple = ()
        else:
            sql = (
                "SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE IN ('BASE TABLE','VIEW') AND TABLE_SCHEMA = %s "
                "ORDER BY TABLE_NAME"
            )
            params = (schema,)
        with self._connection().cursor() as cur:
            cur.execute(sql, params)
            return [(r[0], r[1]) for r in cur.fetchall()]

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        schema = schema or "dbo"
        cols = self._fetch_columns(schema, name)
        pk = self._fetch_primary_key(schema, name)
        fks = self._fetch_foreign_keys(schema, name)
        indexes = self._fetch_indexes(schema, name)
        pk_set = set(pk)
        for c in cols:
            if c.name in pk_set:
                c.is_primary_key = True
        return TableSchema(
            schema=schema, name=name, columns=cols,
            primary_key=pk, foreign_keys=fks, indexes=indexes,
        )

    def _fetch_columns(self, schema: str, table: str) -> list[Column]:
        sql = (
            "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT "
            "FROM INFORMATION_SCHEMA.COLUMNS "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
            "ORDER BY ORDINAL_POSITION"
        )
        with self._connection().cursor() as cur:
            cur.execute(sql, (schema, table))
            return [
                Column(name=r[0], type=r[1], nullable=(r[2] == "YES"), default=r[3])
                for r in cur.fetchall()
            ]

    def _fetch_primary_key(self, schema: str, table: str) -> list[str]:
        sql = (
            "SELECT kcu.COLUMN_NAME "
            "FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc "
            "JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu "
            "  ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME "
            "WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY' "
            "  AND tc.TABLE_SCHEMA = %s AND tc.TABLE_NAME = %s "
            "ORDER BY kcu.ORDINAL_POSITION"
        )
        with self._connection().cursor() as cur:
            cur.execute(sql, (schema, table))
            return [r[0] for r in cur.fetchall()]

    def _fetch_foreign_keys(self, schema: str, table: str) -> list[ForeignKey]:
        sql = """
            SELECT
              fk.name AS constraint_name,
              cp.name AS column_name,
              SCHEMA_NAME(rt.schema_id) AS ref_schema,
              rt.name AS ref_table,
              rc.name AS ref_column,
              fkc.constraint_column_id
            FROM sys.foreign_keys fk
            JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
            JOIN sys.tables t ON fk.parent_object_id = t.object_id
            JOIN sys.columns cp ON cp.object_id = t.object_id AND cp.column_id = fkc.parent_column_id
            JOIN sys.tables rt ON fk.referenced_object_id = rt.object_id
            JOIN sys.columns rc ON rc.object_id = rt.object_id AND rc.column_id = fkc.referenced_column_id
            WHERE SCHEMA_NAME(t.schema_id) = %s AND t.name = %s
            ORDER BY fk.name, fkc.constraint_column_id
        """
        with self._connection().cursor() as cur:
            cur.execute(sql, (schema, table))
            rows = cur.fetchall()
        grouped: dict[str, dict[str, Any]] = {}
        for cname, col, ref_schema, ref_table, ref_col, _ord in rows:
            entry = grouped.setdefault(
                cname,
                {"name": cname, "columns": [], "ref_schema": ref_schema,
                 "ref_table": ref_table, "ref_columns": []},
            )
            entry["columns"].append(col)
            entry["ref_columns"].append(ref_col)
        return [
            ForeignKey(
                columns=g["columns"], referenced_schema=g["ref_schema"],
                referenced_table=g["ref_table"], referenced_columns=g["ref_columns"],
                name=g["name"],
            )
            for g in grouped.values()
        ]

    def _fetch_indexes(self, schema: str, table: str) -> list[Index]:
        sql = """
            SELECT i.name, i.is_unique, c.name, ic.key_ordinal
            FROM sys.indexes i
            JOIN sys.tables t ON i.object_id = t.object_id
            JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
            JOIN sys.columns c ON c.object_id = t.object_id AND c.column_id = ic.column_id
            WHERE SCHEMA_NAME(t.schema_id) = %s AND t.name = %s
              AND i.is_hypothetical = 0 AND i.name IS NOT NULL
            ORDER BY i.name, ic.key_ordinal
        """
        with self._connection().cursor() as cur:
            cur.execute(sql, (schema, table))
            rows = cur.fetchall()
        grouped: dict[str, dict[str, Any]] = {}
        for idx_name, unique, col, _seq in rows:
            entry = grouped.setdefault(idx_name, {"unique": bool(unique), "columns": []})
            entry["columns"].append(col)
        return [Index(name=n, columns=g["columns"], unique=g["unique"]) for n, g in grouped.items()]

    def sample_table(self, name: str, schema: str | None = None, limit: int = 10) -> QueryResult:
        schema = schema or "dbo"
        ident = f"{_quote_ident(schema)}.{_quote_ident(name)}"
        return self._run(f"SELECT TOP {int(limit)} * FROM {ident}", max_rows=limit)

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        if not self.allow_write:
            assert_read_only(sql, dialect=self.dialect)
        return self._run(sql, max_rows=max_rows)

    def explain(self, sql: str) -> str:
        with self._connection().cursor() as cur:
            cur.execute("SET SHOWPLAN_TEXT ON")
            try:
                cur.execute(sql)
                rows = cur.fetchall()
            finally:
                cur.execute("SET SHOWPLAN_TEXT OFF")
        return "\n".join(str(r[0]) for r in rows)

    def _run(self, sql: str, max_rows: int | None = None) -> QueryResult:
        cap = max_rows if max_rows is not None else self.default_max_rows
        start = time.perf_counter()
        with self._connection().cursor() as cur:
            cur.execute(sql)
            cols = [d[0] for d in (cur.description or [])]
            rows: list[list[Any]] = []
            for _ in range(cap + 1):
                row = cur.fetchone()
                if row is None:
                    break
                rows.append(list(row))
        elapsed = (time.perf_counter() - start) * 1000.0
        truncated = len(rows) > cap
        if truncated:
            rows = rows[:cap]
        return QueryResult(columns=cols, rows=rows, row_count=len(rows),
                           truncated=truncated, elapsed_ms=elapsed)

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None

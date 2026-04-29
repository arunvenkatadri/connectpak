"""MySQL connector using PyMySQL."""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import unquote, urlparse

import pymysql

from connectpak.core.base import (
    BaseConnector,
    Column,
    ForeignKey,
    Index,
    QueryResult,
    TableSchema,
)
from connectpak.core.guard import assert_read_only

_SYSTEM_SCHEMAS = ("information_schema", "mysql", "performance_schema", "sys")


def _parse_dsn(dsn: str) -> dict[str, Any]:
    p = urlparse(dsn)
    if p.scheme not in ("mysql", "mariadb", ""):
        raise ValueError(f"unsupported MySQL DSN scheme: {p.scheme!r}")
    return {
        "host": p.hostname or "localhost",
        "port": p.port or 3306,
        "user": unquote(p.username) if p.username else None,
        "password": unquote(p.password) if p.password else None,
        "database": p.path.lstrip("/") or None,
    }


def _quote_ident(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


class MySQLConnector(BaseConnector):
    name = "mysql"
    dialect = "mysql"

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
        self._conn: pymysql.connections.Connection | None = None

    def _connection(self) -> pymysql.connections.Connection:
        if self._conn is not None and self._conn.open:
            return self._conn
        params = _parse_dsn(self.dsn)
        conn = pymysql.connect(autocommit=True, charset="utf8mb4", **params)
        with conn.cursor() as cur:
            cur.execute(f"SET SESSION MAX_EXECUTION_TIME = {int(self.statement_timeout_ms)}")
            if not self.allow_write:
                cur.execute("SET SESSION TRANSACTION READ ONLY")
        self._conn = conn
        return conn

    def list_schemas(self) -> list[str]:
        sql = (
            "SELECT schema_name FROM information_schema.schemata "
            "WHERE schema_name NOT IN %s ORDER BY schema_name"
        )
        with self._connection().cursor() as cur:
            cur.execute(sql, (_SYSTEM_SCHEMAS,))
            return [r[0] for r in cur.fetchall()]

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        if schema is None:
            sql = (
                "SELECT table_schema, table_name FROM information_schema.tables "
                "WHERE table_type IN ('BASE TABLE','VIEW') "
                "AND table_schema NOT IN %s "
                "ORDER BY table_schema, table_name"
            )
            params: tuple = (_SYSTEM_SCHEMAS,)
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
        schema = schema or self._current_database()
        cols = self._fetch_columns(schema, name)
        pk = self._fetch_primary_key(schema, name)
        fks = self._fetch_foreign_keys(schema, name)
        indexes = self._fetch_indexes(schema, name)
        comment = self._fetch_table_comment(schema, name)

        pk_set = set(pk)
        for c in cols:
            if c.name in pk_set:
                c.is_primary_key = True

        return TableSchema(
            schema=schema,
            name=name,
            columns=cols,
            primary_key=pk,
            foreign_keys=fks,
            indexes=indexes,
            comment=comment,
        )

    def _current_database(self) -> str:
        with self._connection().cursor() as cur:
            cur.execute("SELECT DATABASE()")
            row = cur.fetchone()
            if not row or not row[0]:
                raise ValueError("no schema specified and no default database on connection")
            return row[0]

    def _fetch_columns(self, schema: str, table: str) -> list[Column]:
        sql = """
            SELECT column_name, data_type, is_nullable, column_default, column_comment
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        with self._connection().cursor() as cur:
            cur.execute(sql, (schema, table))
            return [
                Column(
                    name=r[0],
                    type=r[1],
                    nullable=(r[2] == "YES"),
                    default=r[3],
                    comment=r[4] or None,
                )
                for r in cur.fetchall()
            ]

    def _fetch_primary_key(self, schema: str, table: str) -> list[str]:
        sql = """
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
             AND tc.table_name = kcu.table_name
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = %s AND tc.table_name = %s
            ORDER BY kcu.ordinal_position
        """
        with self._connection().cursor() as cur:
            cur.execute(sql, (schema, table))
            return [r[0] for r in cur.fetchall()]

    def _fetch_foreign_keys(self, schema: str, table: str) -> list[ForeignKey]:
        sql = """
            SELECT
              kcu.constraint_name,
              kcu.column_name,
              kcu.referenced_table_schema,
              kcu.referenced_table_name,
              kcu.referenced_column_name,
              kcu.ordinal_position
            FROM information_schema.key_column_usage kcu
            WHERE kcu.referenced_table_name IS NOT NULL
              AND kcu.table_schema = %s AND kcu.table_name = %s
            ORDER BY kcu.constraint_name, kcu.ordinal_position
        """
        with self._connection().cursor() as cur:
            cur.execute(sql, (schema, table))
            rows = cur.fetchall()

        grouped: dict[str, dict[str, Any]] = {}
        for cname, col, ref_schema, ref_table, ref_col, _ord in rows:
            entry = grouped.setdefault(
                cname,
                {
                    "name": cname,
                    "columns": [],
                    "ref_schema": ref_schema,
                    "ref_table": ref_table,
                    "ref_columns": [],
                },
            )
            entry["columns"].append(col)
            entry["ref_columns"].append(ref_col)
        return [
            ForeignKey(
                columns=g["columns"],
                referenced_schema=g["ref_schema"],
                referenced_table=g["ref_table"],
                referenced_columns=g["ref_columns"],
                name=g["name"],
            )
            for g in grouped.values()
        ]

    def _fetch_indexes(self, schema: str, table: str) -> list[Index]:
        sql = """
            SELECT index_name, non_unique, column_name, seq_in_index
            FROM information_schema.statistics
            WHERE table_schema = %s AND table_name = %s
            ORDER BY index_name, seq_in_index
        """
        with self._connection().cursor() as cur:
            cur.execute(sql, (schema, table))
            rows = cur.fetchall()
        grouped: dict[str, dict[str, Any]] = {}
        for idx_name, non_unique, col, _seq in rows:
            entry = grouped.setdefault(
                idx_name, {"unique": not bool(non_unique), "columns": []}
            )
            entry["columns"].append(col)
        return [
            Index(name=n, columns=g["columns"], unique=g["unique"])
            for n, g in grouped.items()
        ]

    def _fetch_table_comment(self, schema: str, table: str) -> str | None:
        sql = (
            "SELECT table_comment FROM information_schema.tables "
            "WHERE table_schema = %s AND table_name = %s"
        )
        with self._connection().cursor() as cur:
            cur.execute(sql, (schema, table))
            row = cur.fetchone()
            return (row[0] or None) if row else None

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
        return QueryResult(
            columns=cols,
            rows=[list(r) for r in rows],
            row_count=len(rows),
            truncated=truncated,
            elapsed_ms=elapsed,
        )

    def close(self) -> None:
        if self._conn is not None and self._conn.open:
            self._conn.close()
        self._conn = None

"""Postgres connector using psycopg 3."""

from __future__ import annotations

import time
from typing import Any

import psycopg
from connectpak.core.base import (
    BaseConnector,
    Column,
    ForeignKey,
    Index,
    QueryResult,
    TableSchema,
)
from connectpak.core.guard import assert_read_only
from psycopg import sql as pgsql


class PostgresConnector(BaseConnector):
    name = "postgres"
    dialect = "postgres"

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
        self._conn: psycopg.Connection | None = None

    def _connection(self) -> psycopg.Connection:
        if self._conn is not None and not self._conn.closed:
            return self._conn
        conn = psycopg.connect(self.dsn, autocommit=True)
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = {int(self.statement_timeout_ms)}")
            if not self.allow_write:
                cur.execute("SET default_transaction_read_only = on")
                cur.execute("SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
        self._conn = conn
        return conn

    def list_schemas(self) -> list[str]:
        sql = """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
              AND schema_name NOT LIKE 'pg_%'
            ORDER BY schema_name
        """
        with self._connection().cursor() as cur:
            cur.execute(sql)
            return [r[0] for r in cur.fetchall()]

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        if schema is None:
            sql = """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type IN ('BASE TABLE', 'VIEW')
                  AND table_schema NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
                  AND table_schema NOT LIKE 'pg_%'
                ORDER BY table_schema, table_name
            """
            params: tuple = ()
        else:
            sql = """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type IN ('BASE TABLE', 'VIEW')
                  AND table_schema = %s
                ORDER BY table_name
            """
            params = (schema,)
        with self._connection().cursor() as cur:
            cur.execute(sql, params)
            return [(r[0], r[1]) for r in cur.fetchall()]

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        schema = schema or "public"
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

    def _fetch_columns(self, schema: str, table: str) -> list[Column]:
        sql = """
            SELECT
              c.column_name,
              c.data_type,
              c.is_nullable,
              c.column_default,
              pgd.description
            FROM information_schema.columns c
            LEFT JOIN pg_catalog.pg_statio_all_tables st
              ON st.schemaname = c.table_schema AND st.relname = c.table_name
            LEFT JOIN pg_catalog.pg_description pgd
              ON pgd.objoid = st.relid AND pgd.objsubid = c.ordinal_position
            WHERE c.table_schema = %s AND c.table_name = %s
            ORDER BY c.ordinal_position
        """
        with self._connection().cursor() as cur:
            cur.execute(sql, (schema, table))
            return [
                Column(
                    name=r[0],
                    type=r[1],
                    nullable=(r[2] == "YES"),
                    default=r[3],
                    comment=r[4],
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
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = %s
              AND tc.table_name = %s
            ORDER BY kcu.ordinal_position
        """
        with self._connection().cursor() as cur:
            cur.execute(sql, (schema, table))
            return [r[0] for r in cur.fetchall()]

    def _fetch_foreign_keys(self, schema: str, table: str) -> list[ForeignKey]:
        sql = """
            SELECT
              tc.constraint_name,
              kcu.column_name,
              ccu.table_schema AS ref_schema,
              ccu.table_name AS ref_table,
              ccu.column_name AS ref_column,
              kcu.ordinal_position
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON tc.constraint_name = ccu.constraint_name
             AND tc.table_schema = ccu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = %s
              AND tc.table_name = %s
            ORDER BY tc.constraint_name, kcu.ordinal_position
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
            SELECT
              ic.relname AS index_name,
              i.indisunique,
              array_agg(a.attname ORDER BY array_position(i.indkey, a.attnum)) AS cols
            FROM pg_class tc
            JOIN pg_namespace n ON n.oid = tc.relnamespace
            JOIN pg_index i ON i.indrelid = tc.oid
            JOIN pg_class ic ON ic.oid = i.indexrelid
            JOIN pg_attribute a
              ON a.attrelid = tc.oid AND a.attnum = ANY(i.indkey)
            WHERE n.nspname = %s AND tc.relname = %s
            GROUP BY ic.relname, i.indisunique
            ORDER BY ic.relname
        """
        with self._connection().cursor() as cur:
            cur.execute(sql, (schema, table))
            return [
                Index(name=r[0], columns=list(r[2]), unique=bool(r[1]))
                for r in cur.fetchall()
            ]

    def _fetch_table_comment(self, schema: str, table: str) -> str | None:
        sql = """
            SELECT obj_description(c.oid)
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s AND c.relname = %s
        """
        with self._connection().cursor() as cur:
            cur.execute(sql, (schema, table))
            row = cur.fetchone()
            return row[0] if row else None

    def sample_table(
        self, name: str, schema: str | None = None, limit: int = 10
    ) -> QueryResult:
        if schema:
            ident = pgsql.SQL("{}.{}").format(
                pgsql.Identifier(schema), pgsql.Identifier(name)
            )
        else:
            ident = pgsql.Identifier(name)
        stmt = pgsql.SQL("SELECT * FROM {} LIMIT {}").format(
            ident, pgsql.Literal(int(limit))
        )
        return self._run(stmt, max_rows=limit)

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        if not self.allow_write:
            assert_read_only(sql, dialect=self.dialect)
        return self._run(sql, max_rows=max_rows)

    def explain(self, sql: str) -> str:
        with self._connection().cursor() as cur:
            cur.execute("EXPLAIN " + sql)
            return "\n".join(r[0] for r in cur.fetchall())

    def _run(self, stmt, max_rows: int | None = None) -> QueryResult:
        cap = max_rows if max_rows is not None else self.default_max_rows
        start = time.perf_counter()
        with self._connection().cursor() as cur:
            cur.execute(stmt)
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
        if self._conn is not None and not self._conn.closed:
            self._conn.close()
        self._conn = None

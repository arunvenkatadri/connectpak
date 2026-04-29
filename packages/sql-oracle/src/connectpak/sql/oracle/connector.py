"""Oracle connector using python-oracledb (thin mode, no client library required).

Config: an Oracle Easy Connect string or DSN, prefixed with `user/pass@`.

Examples:
    alice/secret@//db.example.com:1521/ORCLPDB1
    alice/secret@ORCL_TNS_ALIAS

Engine-level read-only:  ALTER SESSION SET ... and SET TRANSACTION READ ONLY
on every new transaction. With autocommit + per-statement implicit
transactions, this approximates session-level read-only.
"""

from __future__ import annotations

import time
from typing import Any

import oracledb

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
    if "@" not in config:
        raise ValueError("oracle config must be 'user/password@dsn'")
    creds, dsn = config.split("@", 1)
    if "/" not in creds:
        raise ValueError("oracle config must be 'user/password@dsn'")
    user, password = creds.split("/", 1)
    return {"user": user, "password": password, "dsn": dsn}


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class OracleConnector(BaseConnector):
    name = "oracle"
    dialect = "oracle"

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
        conn = oracledb.connect(**params)
        conn.autocommit = True
        conn.call_timeout = int(self.statement_timeout_ms)
        if not self.allow_write:
            with conn.cursor() as cur:
                cur.execute("SET TRANSACTION READ ONLY")
        self._conn = conn
        return conn

    def list_schemas(self) -> list[str]:
        sql = (
            "SELECT username FROM all_users "
            "WHERE oracle_maintained = 'N' ORDER BY username"
        )
        with self._connection().cursor() as cur:
            cur.execute(sql)
            return [r[0] for r in cur.fetchall()]

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        if schema is None:
            sql = (
                "SELECT owner, table_name FROM all_tables "
                "WHERE owner NOT IN (SELECT username FROM all_users WHERE oracle_maintained = 'Y') "
                "ORDER BY owner, table_name"
            )
            params: dict = {}
        else:
            sql = (
                "SELECT owner, table_name FROM all_tables WHERE owner = :owner "
                "ORDER BY table_name"
            )
            params = {"owner": schema.upper()}
        with self._connection().cursor() as cur:
            cur.execute(sql, params)
            return [(r[0], r[1]) for r in cur.fetchall()]

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        owner = (schema or self._current_schema()).upper()
        tbl = name.upper()
        cols = self._fetch_columns(owner, tbl)
        pk = self._fetch_primary_key(owner, tbl)
        fks = self._fetch_foreign_keys(owner, tbl)
        indexes = self._fetch_indexes(owner, tbl)
        pk_set = set(pk)
        for c in cols:
            if c.name in pk_set:
                c.is_primary_key = True
        return TableSchema(schema=owner, name=tbl, columns=cols,
                           primary_key=pk, foreign_keys=fks, indexes=indexes)

    def _current_schema(self) -> str:
        with self._connection().cursor() as cur:
            cur.execute("SELECT SYS_CONTEXT('USERENV','CURRENT_SCHEMA') FROM DUAL")
            return cur.fetchone()[0]

    def _fetch_columns(self, owner: str, table: str) -> list[Column]:
        sql = (
            "SELECT column_name, data_type, nullable, data_default "
            "FROM all_tab_columns WHERE owner = :owner AND table_name = :tbl "
            "ORDER BY column_id"
        )
        with self._connection().cursor() as cur:
            cur.execute(sql, {"owner": owner, "tbl": table})
            out: list[Column] = []
            for cname, ctype, nullable, dflt in cur.fetchall():
                default = None
                if dflt is not None:
                    try:
                        default = dflt.read() if hasattr(dflt, "read") else str(dflt)
                    except Exception:
                        default = None
                out.append(Column(name=cname, type=ctype, nullable=(nullable == "Y"), default=default))
            return out

    def _fetch_primary_key(self, owner: str, table: str) -> list[str]:
        sql = (
            "SELECT cc.column_name FROM all_constraints c "
            "JOIN all_cons_columns cc ON c.owner = cc.owner AND c.constraint_name = cc.constraint_name "
            "WHERE c.constraint_type = 'P' AND c.owner = :owner AND c.table_name = :tbl "
            "ORDER BY cc.position"
        )
        with self._connection().cursor() as cur:
            cur.execute(sql, {"owner": owner, "tbl": table})
            return [r[0] for r in cur.fetchall()]

    def _fetch_foreign_keys(self, owner: str, table: str) -> list[ForeignKey]:
        sql = (
            "SELECT c.constraint_name, cc.column_name, "
            "       rc.owner AS r_owner, rc.table_name AS r_table, rcc.column_name AS r_column, "
            "       cc.position "
            "FROM all_constraints c "
            "JOIN all_cons_columns cc ON c.owner=cc.owner AND c.constraint_name=cc.constraint_name "
            "JOIN all_constraints rc ON c.r_owner=rc.owner AND c.r_constraint_name=rc.constraint_name "
            "JOIN all_cons_columns rcc ON rc.owner=rcc.owner AND rc.constraint_name=rcc.constraint_name "
            "                          AND cc.position=rcc.position "
            "WHERE c.constraint_type='R' AND c.owner=:owner AND c.table_name=:tbl "
            "ORDER BY c.constraint_name, cc.position"
        )
        with self._connection().cursor() as cur:
            cur.execute(sql, {"owner": owner, "tbl": table})
            rows = cur.fetchall()
        grouped: dict[str, dict[str, Any]] = {}
        for cname, col, r_owner, r_table, r_col, _pos in rows:
            entry = grouped.setdefault(
                cname, {"name": cname, "columns": [], "ref_schema": r_owner,
                        "ref_table": r_table, "ref_columns": []},
            )
            entry["columns"].append(col)
            entry["ref_columns"].append(r_col)
        return [
            ForeignKey(columns=g["columns"], referenced_schema=g["ref_schema"],
                       referenced_table=g["ref_table"], referenced_columns=g["ref_columns"],
                       name=g["name"])
            for g in grouped.values()
        ]

    def _fetch_indexes(self, owner: str, table: str) -> list[Index]:
        sql = (
            "SELECT i.index_name, i.uniqueness, ic.column_name, ic.column_position "
            "FROM all_indexes i "
            "JOIN all_ind_columns ic ON i.owner=ic.index_owner AND i.index_name=ic.index_name "
            "WHERE i.table_owner=:owner AND i.table_name=:tbl "
            "ORDER BY i.index_name, ic.column_position"
        )
        with self._connection().cursor() as cur:
            cur.execute(sql, {"owner": owner, "tbl": table})
            rows = cur.fetchall()
        grouped: dict[str, dict[str, Any]] = {}
        for idx_name, uniq, col, _pos in rows:
            entry = grouped.setdefault(idx_name, {"unique": uniq == "UNIQUE", "columns": []})
            entry["columns"].append(col)
        return [Index(name=n, columns=g["columns"], unique=g["unique"]) for n, g in grouped.items()]

    def sample_table(self, name: str, schema: str | None = None, limit: int = 10) -> QueryResult:
        ident = _quote_ident(name.upper())
        if schema:
            ident = f"{_quote_ident(schema.upper())}.{ident}"
        return self._run(f"SELECT * FROM {ident} FETCH FIRST {int(limit)} ROWS ONLY", max_rows=limit)

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        if not self.allow_write:
            assert_read_only(sql, dialect=self.dialect)
        return self._run(sql, max_rows=max_rows)

    def explain(self, sql: str) -> str:
        with self._connection().cursor() as cur:
            cur.execute("EXPLAIN PLAN FOR " + sql)
            cur.execute("SELECT plan_table_output FROM TABLE(DBMS_XPLAN.DISPLAY)")
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

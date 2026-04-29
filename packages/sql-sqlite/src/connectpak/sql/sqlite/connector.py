"""SQLite connector using stdlib sqlite3."""

from __future__ import annotations

import sqlite3
import time
from urllib.parse import quote

from connectpak.core.base import (
    BaseConnector,
    Column,
    ForeignKey,
    Index,
    QueryResult,
    TableSchema,
)
from connectpak.core.guard import assert_read_only


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class SqliteConnector(BaseConnector):
    name = "sqlite"
    dialect = "sqlite"

    def __init__(
        self,
        path: str,
        *,
        allow_write: bool = False,
        statement_timeout_ms: int = 30_000,
        default_max_rows: int = 1000,
    ):
        self.path = path
        self.allow_write = allow_write
        self.statement_timeout_ms = statement_timeout_ms
        self.default_max_rows = default_max_rows
        self._conn: sqlite3.Connection | None = None

    def _connection(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn
        if self.path == ":memory:" or self.allow_write:
            conn = sqlite3.connect(self.path)
        else:
            uri = f"file:{quote(self.path)}?mode=ro"
            conn = sqlite3.connect(uri, uri=True)
        conn.execute(f"PRAGMA busy_timeout = {int(self.statement_timeout_ms)}")
        self._conn = conn
        return conn

    def list_schemas(self) -> list[str]:
        return ["main"]

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        cur = self._connection().execute(
            "SELECT name FROM sqlite_master "
            "WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
        return [("main", r[0]) for r in cur.fetchall()]

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        conn = self._connection()
        ident = _quote_ident(name)

        info = conn.execute(f"PRAGMA table_info({ident})").fetchall()
        # cid, name, type, notnull, dflt_value, pk
        cols: list[Column] = []
        pk: list[tuple[int, str]] = []
        for cid, cname, ctype, notnull, default, pk_pos in info:
            cols.append(
                Column(
                    name=cname,
                    type=ctype or "",
                    nullable=(not bool(notnull)),
                    default=default,
                    is_primary_key=bool(pk_pos),
                )
            )
            if pk_pos:
                pk.append((pk_pos, cname))
        pk_cols = [n for _, n in sorted(pk)]

        fk_rows = conn.execute(f"PRAGMA foreign_key_list({ident})").fetchall()
        # id, seq, table, from, to, on_update, on_delete, match
        fk_groups: dict[int, dict] = {}
        for fk_id, _seq, ref_table, from_col, to_col, *_rest in fk_rows:
            entry = fk_groups.setdefault(
                fk_id,
                {"columns": [], "ref_table": ref_table, "ref_columns": []},
            )
            entry["columns"].append(from_col)
            entry["ref_columns"].append(to_col)
        fks = [
            ForeignKey(
                columns=g["columns"],
                referenced_schema=None,
                referenced_table=g["ref_table"],
                referenced_columns=g["ref_columns"],
            )
            for g in fk_groups.values()
        ]

        idx_list = conn.execute(f"PRAGMA index_list({ident})").fetchall()
        # seq, name, unique, origin, partial
        indexes: list[Index] = []
        for _seq, idx_name, unique, *_rest in idx_list:
            idx_info = conn.execute(
                f"PRAGMA index_info({_quote_ident(idx_name)})"
            ).fetchall()
            # seqno, cid, name
            idx_cols = [r[2] for r in sorted(idx_info, key=lambda r: r[0])]
            indexes.append(Index(name=idx_name, columns=idx_cols, unique=bool(unique)))

        return TableSchema(
            schema="main",
            name=name,
            columns=cols,
            primary_key=pk_cols,
            foreign_keys=fks,
            indexes=indexes,
        )

    def sample_table(
        self, name: str, schema: str | None = None, limit: int = 10
    ) -> QueryResult:
        ident = _quote_ident(name)
        sql = f"SELECT * FROM {ident} LIMIT ?"
        return self._run(sql, (int(limit),), max_rows=limit)

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        if not self.allow_write:
            assert_read_only(sql, dialect=self.dialect)
        return self._run(sql, (), max_rows=max_rows)

    def explain(self, sql: str) -> str:
        cur = self._connection().execute("EXPLAIN QUERY PLAN " + sql)
        rows = cur.fetchall()
        return "\n".join(" | ".join(str(c) for c in r) for r in rows)

    def _run(self, sql: str, params: tuple, max_rows: int | None) -> QueryResult:
        cap = max_rows if max_rows is not None else self.default_max_rows
        start = time.perf_counter()
        cur = self._connection().execute(sql, params)
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
        if self._conn is not None:
            self._conn.close()
        self._conn = None

"""Cassandra connector using cassandra-driver.

Config: comma-separated contact points, optionally with credentials and port:
    127.0.0.1,10.0.0.5
    user:pass@127.0.0.1:9042

Mapping:
- list_schemas() -> keyspaces (excluding system_*).
- list_tables(schema) -> tables in the keyspace.
- describe_table(name, schema) -> columns + partition/clustering as PK.
- query(sql, ...) -> raw CQL with a write-keyword guard.
"""

from __future__ import annotations

import time
from typing import Any

from connectpak.core.base import (
    BaseConnector,
    Column,
    QueryResult,
    TableSchema,
)
from connectpak.core.guard import assert_no_write_keywords

from cassandra.auth import PlainTextAuthProvider
from cassandra.cluster import Cluster

_SYSTEM_KEYSPACES = {
    "system", "system_auth", "system_distributed", "system_schema",
    "system_traces", "system_views", "system_virtual_schema",
}
_CQL_WRITE_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "CREATE", "ALTER", "TRUNCATE",
    "GRANT", "REVOKE", "BATCH",
)


def _parse_config(config: str) -> dict[str, Any]:
    user = password = None
    rest = config
    if "@" in rest:
        creds, rest = rest.split("@", 1)
        if ":" in creds:
            user, password = creds.split(":", 1)
        else:
            user = creds
    port = 9042
    if ":" in rest.split(",")[-1]:
        last, port_s = rest.rsplit(":", 1)
        try:
            port = int(port_s)
            rest = last
        except ValueError:
            pass
    contacts = [h.strip() for h in rest.split(",") if h.strip()]
    return {
        "contact_points": contacts or ["127.0.0.1"],
        "port": port,
        "user": user,
        "password": password,
    }


class CassandraConnector(BaseConnector):
    name = "cassandra"
    dialect = None

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
        self._cluster: Cluster | None = None
        self._session: Any = None

    def _connection(self) -> Any:
        if self._session is not None:
            return self._session
        params = _parse_config(self.config)
        auth = None
        if params["user"]:
            auth = PlainTextAuthProvider(username=params["user"], password=params["password"] or "")
        self._cluster = Cluster(
            contact_points=params["contact_points"],
            port=params["port"],
            auth_provider=auth,
        )
        self._session = self._cluster.connect()
        self._session.default_timeout = max(1.0, self.statement_timeout_ms / 1000.0)
        return self._session

    def list_schemas(self) -> list[str]:
        rows = self._connection().execute(
            "SELECT keyspace_name FROM system_schema.keyspaces"
        )
        return sorted(r.keyspace_name for r in rows if r.keyspace_name not in _SYSTEM_KEYSPACES)

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        if schema is None:
            rows = self._connection().execute(
                "SELECT keyspace_name, table_name FROM system_schema.tables"
            )
            return sorted(
                [(r.keyspace_name, r.table_name) for r in rows
                 if r.keyspace_name not in _SYSTEM_KEYSPACES],
                key=lambda x: (x[0], x[1]),
            )
        rows = self._connection().execute(
            "SELECT keyspace_name, table_name FROM system_schema.tables WHERE keyspace_name = %s",
            (schema,),
        )
        return sorted([(r.keyspace_name, r.table_name) for r in rows], key=lambda x: x[1])

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        if schema is None:
            raise ValueError("Cassandra describe_table requires a keyspace (schema)")
        rows = self._connection().execute(
            "SELECT column_name, type, kind, position FROM system_schema.columns "
            "WHERE keyspace_name=%s AND table_name=%s",
            (schema, name),
        )
        cols: list[Column] = []
        pk: list[tuple[int, str]] = []
        for r in rows:
            is_pk = r.kind in ("partition_key", "clustering")
            cols.append(Column(name=r.column_name, type=r.type, nullable=not is_pk,
                               is_primary_key=is_pk))
            if is_pk:
                pk.append((r.position, r.column_name))
        pk_cols = [n for _, n in sorted(pk)]
        return TableSchema(schema=schema, name=name, columns=cols,
                           primary_key=pk_cols, foreign_keys=[], indexes=[])

    def sample_table(self, name: str, schema: str | None = None, limit: int = 10) -> QueryResult:
        if schema is None:
            raise ValueError("Cassandra sample_table requires a keyspace (schema)")
        cql = f'SELECT * FROM "{schema}"."{name}" LIMIT {int(limit)}'
        return self._run(cql, max_rows=limit)

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        if not self.allow_write:
            assert_no_write_keywords(sql, _CQL_WRITE_KEYWORDS)
        return self._run(sql, max_rows=max_rows)

    def explain(self, sql: str) -> str:
        # Cassandra does not have a true EXPLAIN; TRACING ON gives runtime info
        # only. Return the keyspace/table plan summary instead.
        return f"Cassandra has no EXPLAIN; CQL accepted: {sql.strip()[:200]}"

    def _run(self, cql: str, max_rows: int | None = None) -> QueryResult:
        cap = max_rows if max_rows is not None else self.default_max_rows
        start = time.perf_counter()
        result = self._connection().execute(cql)
        all_rows: list[Any] = []
        for r in result:
            all_rows.append(r)
            if len(all_rows) >= cap + 1:
                break
        elapsed = (time.perf_counter() - start) * 1000.0
        cols = list(result.column_names) if hasattr(result, "column_names") else (
            list(all_rows[0]._fields) if all_rows else []
        )
        truncated = len(all_rows) > cap
        if truncated:
            all_rows = all_rows[:cap]
        rows = [[getattr(r, c, None) for c in cols] for r in all_rows]
        return QueryResult(columns=cols, rows=rows, row_count=len(rows),
                           truncated=truncated, elapsed_ms=elapsed)

    def close(self) -> None:
        if self._cluster is not None:
            try:
                self._cluster.shutdown()
            except Exception:
                pass
        self._session = None
        self._cluster = None

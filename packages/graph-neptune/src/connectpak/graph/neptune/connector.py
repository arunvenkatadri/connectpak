"""Amazon Neptune connector using gremlinpython (Gremlin/WebSocket).

Config: a Gremlin server URL, e.g.
    wss://my-neptune-cluster.cluster-xxxx.us-east-1.neptune.amazonaws.com:8182/gremlin

Mapping (graph -> connector):
- list_schemas() -> ["nodes", "relationships"]
- list_tables("nodes") -> distinct vertex labels
- list_tables("relationships") -> distinct edge labels
- describe_table -> property keys for the label (sample-based)
- query(gremlin, ...) -> raw Gremlin traversal string with read-only check
                        (rejects addV, addE, drop, property writes).
"""

from __future__ import annotations

import time
from typing import Any

from gremlin_python.driver.driver_remote_connection import DriverRemoteConnection
from gremlin_python.process.anonymous_traversal import traversal
from gremlin_python.process.graph_traversal import __  # type: ignore[attr-defined]

from connectpak.core.base import (
    BaseConnector,
    Column,
    QueryResult,
    TableSchema,
)
from connectpak.core.guard import assert_no_write_keywords

_GREMLIN_WRITE_KEYWORDS = ("addV", "addE", "drop", "property")


class NeptuneConnector(BaseConnector):
    name = "neptune"
    dialect = None

    def __init__(
        self,
        config: str,
        *,
        allow_write: bool = False,
        statement_timeout_ms: int = 30_000,
        default_max_rows: int = 1000,
    ):
        self.url = config
        self.allow_write = allow_write
        self.statement_timeout_ms = statement_timeout_ms
        self.default_max_rows = default_max_rows
        self._conn: DriverRemoteConnection | None = None
        self._g: Any = None

    def _connection(self):
        if self._g is not None:
            return self._g
        self._conn = DriverRemoteConnection(self.url, "g")
        self._g = traversal().withRemote(self._conn)
        return self._g

    def list_schemas(self) -> list[str]:
        return ["nodes", "relationships"]

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        g = self._connection()
        out: list[tuple[str | None, str]] = []
        if schema in (None, "nodes"):
            for label in g.V().label().dedup().toList():
                out.append(("nodes", label))
        if schema in (None, "relationships"):
            for label in g.E().label().dedup().toList():
                out.append(("relationships", label))
        return sorted(out, key=lambda x: (x[0] or "", x[1]))

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        schema = schema or "nodes"
        g = self._connection()
        if schema == "nodes":
            sample = g.V().hasLabel(name).limit(50).valueMap(True).toList()
        else:
            sample = g.E().hasLabel(name).limit(50).valueMap(True).toList()
        keys: dict[str, str] = {}
        for vmap in sample:
            for k, v in vmap.items():
                key = str(k)
                if key in keys:
                    continue
                if isinstance(v, list) and v:
                    keys[key] = type(v[0]).__name__
                else:
                    keys[key] = type(v).__name__
        cols = [Column(name=k, type=t, nullable=True) for k, t in keys.items()]
        return TableSchema(schema=schema, name=name, columns=cols,
                           primary_key=[], foreign_keys=[], indexes=[])

    def sample_table(self, name: str, schema: str | None = None, limit: int = 10) -> QueryResult:
        schema = schema or "nodes"
        g = self._connection()
        start = time.perf_counter()
        if schema == "nodes":
            data = g.V().hasLabel(name).limit(int(limit)).valueMap(True).toList()
        else:
            data = g.E().hasLabel(name).limit(int(limit)).valueMap(True).toList()
        elapsed = (time.perf_counter() - start) * 1000.0
        return self._maps_to_result(data, elapsed, truncated=False)

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        if not self.allow_write:
            assert_no_write_keywords(sql, _GREMLIN_WRITE_KEYWORDS)
        cap = max_rows if max_rows is not None else self.default_max_rows
        # gremlinpython exposes a string-based submit via the underlying client.
        client = self._connection().connection.client  # type: ignore[attr-defined]
        start = time.perf_counter()
        result = client.submit(sql).all().result(timeout=self.statement_timeout_ms / 1000.0)
        elapsed = (time.perf_counter() - start) * 1000.0
        rows: list[Any] = list(result)
        truncated = len(rows) > cap
        if truncated:
            rows = rows[:cap]
        return self._maps_to_result(rows, elapsed, truncated=truncated)

    def explain(self, sql: str) -> str:
        return f"Neptune Gremlin does not have a portable EXPLAIN; query: {sql.strip()[:200]}"

    def _maps_to_result(self, items: list[Any], elapsed_ms: float, *, truncated: bool) -> QueryResult:
        cols: list[str] = []
        seen: set[str] = set()
        norm: list[dict[str, Any]] = []
        for it in items:
            if isinstance(it, dict):
                d = {str(k): (v[0] if isinstance(v, list) and len(v) == 1 else v) for k, v in it.items()}
            else:
                d = {"value": it}
            norm.append(d)
            for k in d:
                if k not in seen:
                    seen.add(k)
                    cols.append(k)
        rows = [[self._jsonable(d.get(c)) for c in cols] for d in norm]
        return QueryResult(columns=cols, rows=rows, row_count=len(rows),
                           truncated=truncated, elapsed_ms=elapsed_ms)

    @staticmethod
    def _jsonable(v: Any) -> Any:
        if isinstance(v, (str, int, float, bool, type(None))):
            return v
        if isinstance(v, (list, dict)):
            return v
        return str(v)

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None
        self._g = None

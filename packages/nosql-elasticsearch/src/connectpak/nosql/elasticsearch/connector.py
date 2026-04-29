"""Elasticsearch connector using the official `elasticsearch` client.

Config: a URL like  http://elastic:pass@localhost:9200

Mapping:
- list_schemas() -> ["_indices"] (no schema concept)
- list_tables() -> indices (excluding hidden ones)
- describe_table(name) -> mapping fields as columns
- sample_table(name, limit) -> match_all search with size=limit
- query(sql, max_rows) -> JSON spec:
      {"op": "search", "index": "x", "body": {"query": {...}}, "size": N}
      {"op": "sql",    "query": "SELECT ..."}            # Elasticsearch SQL
      {"op": "esql",   "query": "FROM idx | LIMIT 10"}   # ES|QL
"""

from __future__ import annotations

import json
import time
from typing import Any

from elasticsearch import Elasticsearch

from connectpak.core.base import (
    BaseConnector,
    Column,
    QueryResult,
    TableSchema,
)
from connectpak.core.guard import WriteOperationError, assert_read_only

_READ_OPS = {"search", "count", "sql", "esql"}


class ElasticsearchConnector(BaseConnector):
    name = "elasticsearch"
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
        self._client: Elasticsearch | None = None

    def _connection(self) -> Elasticsearch:
        if self._client is not None:
            return self._client
        self._client = Elasticsearch(
            self.url,
            request_timeout=max(1.0, self.statement_timeout_ms / 1000.0),
        )
        return self._client

    def list_schemas(self) -> list[str]:
        return ["_indices"]

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        resp = self._connection().cat.indices(format="json", h="index")
        out: list[tuple[str | None, str]] = []
        for r in resp:
            idx = r["index"]
            if not idx.startswith("."):
                out.append(("_indices", idx))
        return sorted(out, key=lambda x: x[1])

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        mapping = self._connection().indices.get_mapping(index=name)
        body = mapping[name]["mappings"].get("properties", {})
        cols = [
            Column(name=k, type=v.get("type", "object"), nullable=True)
            for k, v in body.items()
        ]
        return TableSchema(schema="_indices", name=name, columns=cols,
                           primary_key=[], foreign_keys=[], indexes=[])

    def sample_table(self, name: str, schema: str | None = None, limit: int = 10) -> QueryResult:
        start = time.perf_counter()
        resp = self._connection().search(index=name, size=int(limit), query={"match_all": {}})
        elapsed = (time.perf_counter() - start) * 1000.0
        hits = [h["_source"] for h in resp["hits"]["hits"]]
        return self._docs_to_result(hits, elapsed, truncated=False)

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        spec = self._parse_spec(sql)
        cap = max_rows if max_rows is not None else self.default_max_rows
        op = spec["op"]
        client = self._connection()
        start = time.perf_counter()
        if op == "search":
            resp = client.search(
                index=spec["index"],
                size=min(cap + 1, spec.get("size", cap + 1)),
                **{k: v for k, v in spec.get("body", {}).items()},
            )
            hits = [h["_source"] for h in resp["hits"]["hits"]]
            elapsed = (time.perf_counter() - start) * 1000.0
            truncated = len(hits) > cap
            if truncated:
                hits = hits[:cap]
            return self._docs_to_result(hits, elapsed, truncated=truncated)
        if op == "count":
            resp = client.count(index=spec["index"], **spec.get("body", {}))
            elapsed = (time.perf_counter() - start) * 1000.0
            return QueryResult(columns=["count"], rows=[[resp["count"]]],
                               row_count=1, truncated=False, elapsed_ms=elapsed)
        if op == "sql":
            stmt = spec["query"]
            if not self.allow_write:
                assert_read_only(stmt, dialect=None)
            resp = client.sql.query(query=stmt, fetch_size=cap + 1)
            cols = [c["name"] for c in resp.get("columns", [])]
            rows = [list(r) for r in resp.get("rows", [])]
            elapsed = (time.perf_counter() - start) * 1000.0
            truncated = len(rows) > cap
            if truncated:
                rows = rows[:cap]
            return QueryResult(columns=cols, rows=rows, row_count=len(rows),
                               truncated=truncated, elapsed_ms=elapsed)
        if op == "esql":
            stmt = spec["query"]
            self._guard_esql(stmt)
            resp = client.esql.query(query=stmt)
            cols = [c["name"] for c in resp.get("columns", [])]
            rows = [list(r) for r in resp.get("values", [])]
            elapsed = (time.perf_counter() - start) * 1000.0
            truncated = len(rows) > cap
            if truncated:
                rows = rows[:cap]
            return QueryResult(columns=cols, rows=rows, row_count=len(rows),
                               truncated=truncated, elapsed_ms=elapsed)
        raise WriteOperationError(f"unsupported Elasticsearch op: {op!r}")

    def explain(self, sql: str) -> str:
        spec = self._parse_spec(sql)
        if spec["op"] == "sql":
            resp = self._connection().sql.translate(query=spec["query"])
            return json.dumps(dict(resp), default=str, indent=2)
        return f"explain not supported for op={spec['op']!r}"

    def _parse_spec(self, sql: str) -> dict[str, Any]:
        if not sql or not sql.strip():
            raise WriteOperationError("empty query")
        try:
            spec = json.loads(sql)
        except json.JSONDecodeError as e:
            raise WriteOperationError(f"Elasticsearch query must be JSON: {e}") from e
        if not isinstance(spec, dict) or "op" not in spec:
            raise WriteOperationError("Elasticsearch query must include 'op'")
        if not self.allow_write and spec["op"] not in _READ_OPS:
            raise WriteOperationError(f"op {spec['op']!r} is not read-only")
        return spec

    def _guard_esql(self, esql: str) -> None:
        if self.allow_write:
            return
        # ES|QL is read-only by design (no INSERT/UPDATE/DELETE), but reject
        # the few processing commands that can mutate cluster state.
        from connectpak.core.guard import assert_no_write_keywords
        assert_no_write_keywords(esql, ("INSERT", "UPDATE", "DELETE", "DROP", "CREATE"))

    def _docs_to_result(self, docs: list[dict], elapsed_ms: float, *, truncated: bool) -> QueryResult:
        cols: list[str] = []
        seen: set[str] = set()
        for d in docs:
            for k in d.keys():
                if k not in seen:
                    seen.add(k)
                    cols.append(k)
        rows = [[d.get(c) for c in cols] for d in docs]
        return QueryResult(columns=cols, rows=rows, row_count=len(rows),
                           truncated=truncated, elapsed_ms=elapsed_ms)

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
        self._client = None

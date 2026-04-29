"""Pinecone connector using pinecone-client (v4 SDK).

Config: a Pinecone API key.

Mapping:
- list_schemas() -> ["pinecone"]
- list_tables() -> indexes in the project
- describe_table(name) -> a single `vector` Column with the index dimension
- sample_table(name, limit) -> not natively supported; returns empty.
- query(sql, max_rows) -> JSON spec:
      {"index": "x", "vector": [...], "top_k": N, "filter": {...},
       "namespace": "...", "include_metadata": true}
  Read-only by definition (Pinecone's data plane writes use upsert/delete,
  which are not exposed here).
"""

from __future__ import annotations

import json
import time
from typing import Any

from pinecone import Pinecone

from connectpak.core.base import (
    BaseConnector,
    Column,
    QueryResult,
    TableSchema,
)
from connectpak.core.guard import WriteOperationError


class PineconeConnector(BaseConnector):
    name = "pinecone"
    dialect = None

    def __init__(
        self,
        config: str,
        *,
        allow_write: bool = False,
        statement_timeout_ms: int = 30_000,
        default_max_rows: int = 1000,
    ):
        self.api_key = config
        self.allow_write = allow_write
        self.statement_timeout_ms = statement_timeout_ms
        self.default_max_rows = default_max_rows
        self._client: Pinecone | None = None
        self._index_cache: dict[str, Any] = {}

    def _connection(self) -> Pinecone:
        if self._client is not None:
            return self._client
        self._client = Pinecone(api_key=self.api_key)
        return self._client

    def list_schemas(self) -> list[str]:
        return ["pinecone"]

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        return [("pinecone", idx.name) for idx in self._connection().list_indexes()]

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        info = self._connection().describe_index(name)
        dim = getattr(info, "dimension", None) or info["dimension"]
        metric = getattr(info, "metric", None) or info.get("metric")
        cols = [
            Column(name="id", type="string", nullable=False, is_primary_key=True),
            Column(name="vector", type=f"vector({dim})", nullable=False),
            Column(name="metadata", type="object", nullable=True),
        ]
        return TableSchema(
            schema="pinecone", name=name, columns=cols,
            primary_key=["id"], foreign_keys=[], indexes=[],
            comment=f"metric={metric}",
        )

    def sample_table(self, name: str, schema: str | None = None, limit: int = 10) -> QueryResult:
        # Pinecone does not have a "scan all" primitive in the data plane.
        return QueryResult(columns=["id", "vector", "metadata"], rows=[],
                           row_count=0, truncated=False, elapsed_ms=0.0)

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        spec = self._parse_spec(sql)
        cap = max_rows if max_rows is not None else self.default_max_rows
        idx_name = spec["index"]
        idx = self._index_cache.get(idx_name) or self._connection().Index(idx_name)
        self._index_cache[idx_name] = idx
        top_k = min(int(spec.get("top_k", cap)), cap + 1)

        kwargs: dict[str, Any] = {"top_k": top_k}
        if "vector" in spec:
            kwargs["vector"] = spec["vector"]
        elif "id" in spec:
            kwargs["id"] = spec["id"]
        else:
            raise WriteOperationError("query spec needs 'vector' or 'id'")
        if "namespace" in spec:
            kwargs["namespace"] = spec["namespace"]
        if "filter" in spec:
            kwargs["filter"] = spec["filter"]
        kwargs["include_metadata"] = bool(spec.get("include_metadata", True))
        kwargs["include_values"] = bool(spec.get("include_values", False))

        start = time.perf_counter()
        resp = idx.query(**kwargs)
        elapsed = (time.perf_counter() - start) * 1000.0

        matches = resp.get("matches", []) if isinstance(resp, dict) else getattr(resp, "matches", [])
        rows: list[list[Any]] = []
        for m in matches:
            mid = m["id"] if isinstance(m, dict) else m.id
            score = m.get("score") if isinstance(m, dict) else m.score
            md = m.get("metadata") if isinstance(m, dict) else getattr(m, "metadata", None)
            rows.append([mid, score, md])
        truncated = len(rows) > cap
        if truncated:
            rows = rows[:cap]
        return QueryResult(columns=["id", "score", "metadata"], rows=rows,
                           row_count=len(rows), truncated=truncated, elapsed_ms=elapsed)

    def explain(self, sql: str) -> str:
        spec = self._parse_spec(sql)
        return f"Pinecone has no EXPLAIN. Spec: index={spec.get('index')}, top_k={spec.get('top_k')}"

    def _parse_spec(self, sql: str) -> dict[str, Any]:
        if not sql or not sql.strip():
            raise WriteOperationError("empty query")
        try:
            spec = json.loads(sql)
        except json.JSONDecodeError as e:
            raise WriteOperationError(f"Pinecone query must be JSON: {e}") from e
        if not isinstance(spec, dict) or "index" not in spec:
            raise WriteOperationError("Pinecone query must include 'index'")
        return spec

    def close(self) -> None:
        self._index_cache.clear()
        self._client = None

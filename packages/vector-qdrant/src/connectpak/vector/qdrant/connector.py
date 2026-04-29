"""Qdrant connector using qdrant-client.

Config: a Qdrant URL, e.g.
    http://localhost:6333
    https://api-key@my-cluster.qdrant.io

Mapping:
- list_schemas() -> ["qdrant"]
- list_tables() -> collections
- describe_table(name) -> vector size + distance metric + payload schema
- sample_table(name, limit) -> first `limit` points (scroll)
- query(sql, max_rows) -> JSON spec:
      {"collection": "x", "vector": [...], "limit": N, "filter": {...},
       "with_payload": true}
"""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import unquote, urlparse

from qdrant_client import QdrantClient

from connectpak.core.base import (
    BaseConnector,
    Column,
    QueryResult,
    TableSchema,
)
from connectpak.core.guard import WriteOperationError


def _parse_config(config: str) -> dict[str, Any]:
    p = urlparse(config)
    api_key = unquote(p.username) if p.username else None
    if not api_key and p.password:
        api_key = unquote(p.password)
    netloc = p.hostname or "localhost"
    if p.port:
        netloc += f":{p.port}"
    url = f"{p.scheme or 'http'}://{netloc}{p.path}"
    return {"url": url, "api_key": api_key}


class QdrantConnector(BaseConnector):
    name = "qdrant"
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
        self._client: QdrantClient | None = None

    def _connection(self) -> QdrantClient:
        if self._client is not None:
            return self._client
        params = _parse_config(self.config)
        self._client = QdrantClient(
            url=params["url"], api_key=params["api_key"],
            timeout=max(1.0, self.statement_timeout_ms / 1000.0),
        )
        return self._client

    def list_schemas(self) -> list[str]:
        return ["qdrant"]

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        cols = self._connection().get_collections().collections
        return [("qdrant", c.name) for c in cols]

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        info = self._connection().get_collection(name)
        cfg = info.config
        params = cfg.params.vectors
        size = getattr(params, "size", None)
        distance = getattr(params, "distance", None)
        cols = [
            Column(name="id", type="string", nullable=False, is_primary_key=True),
            Column(name="vector", type=f"vector({size})" if size else "vector", nullable=False),
            Column(name="payload", type="object", nullable=True),
        ]
        return TableSchema(
            schema="qdrant", name=name, columns=cols,
            primary_key=["id"], foreign_keys=[], indexes=[],
            comment=f"distance={distance}",
        )

    def sample_table(self, name: str, schema: str | None = None, limit: int = 10) -> QueryResult:
        client = self._connection()
        start = time.perf_counter()
        points, _ = client.scroll(collection_name=name, limit=int(limit), with_payload=True)
        elapsed = (time.perf_counter() - start) * 1000.0
        return self._points_to_result(points, elapsed, truncated=False, with_score=False)

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        spec = self._parse_spec(sql)
        cap = max_rows if max_rows is not None else self.default_max_rows
        client = self._connection()
        limit = min(int(spec.get("limit", cap)), cap + 1)
        start = time.perf_counter()
        if "vector" in spec:
            results = client.search(
                collection_name=spec["collection"],
                query_vector=spec["vector"],
                limit=limit,
                query_filter=spec.get("filter"),
                with_payload=spec.get("with_payload", True),
            )
            elapsed = (time.perf_counter() - start) * 1000.0
            truncated = len(results) > cap
            if truncated:
                results = results[:cap]
            return self._points_to_result(results, elapsed, truncated=truncated, with_score=True)
        # default: scroll
        points, _ = client.scroll(
            collection_name=spec["collection"],
            limit=limit,
            scroll_filter=spec.get("filter"),
            with_payload=spec.get("with_payload", True),
        )
        elapsed = (time.perf_counter() - start) * 1000.0
        truncated = len(points) > cap
        if truncated:
            points = points[:cap]
        return self._points_to_result(points, elapsed, truncated=truncated, with_score=False)

    def explain(self, sql: str) -> str:
        spec = self._parse_spec(sql)
        return f"Qdrant has no EXPLAIN. Spec: collection={spec.get('collection')}"

    def _parse_spec(self, sql: str) -> dict[str, Any]:
        if not sql or not sql.strip():
            raise WriteOperationError("empty query")
        try:
            spec = json.loads(sql)
        except json.JSONDecodeError as e:
            raise WriteOperationError(f"Qdrant query must be JSON: {e}") from e
        if not isinstance(spec, dict) or "collection" not in spec:
            raise WriteOperationError("Qdrant query must include 'collection'")
        return spec

    def _points_to_result(self, points: list[Any], elapsed_ms: float,
                          *, truncated: bool, with_score: bool) -> QueryResult:
        cols = ["id"] + (["score"] if with_score else []) + ["payload"]
        rows = []
        for p in points:
            row = [p.id]
            if with_score:
                row.append(getattr(p, "score", None))
            row.append(getattr(p, "payload", None))
            rows.append(row)
        return QueryResult(columns=cols, rows=rows, row_count=len(rows),
                           truncated=truncated, elapsed_ms=elapsed_ms)

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
        self._client = None

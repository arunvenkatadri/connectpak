"""Weaviate connector using weaviate-client v4.

Config: a Weaviate URL, e.g.
    http://localhost:8080
    https://my-cluster.weaviate.network

Mapping (Weaviate "collection" -> "table"):
- list_schemas() -> ["weaviate"]
- list_tables() -> collection names
- describe_table(name) -> properties of the collection
- sample_table(name, limit) -> first `limit` objects (no vector search)
- query(sql, max_rows) -> JSON spec:
      {"collection": "x", "near_vector": [...], "limit": N,
       "where": {...}, "return_metadata": ["distance", "score"]}
"""

from __future__ import annotations

import json
import time
from typing import Any

from connectpak.core.base import (
    BaseConnector,
    Column,
    QueryResult,
    TableSchema,
)
from connectpak.core.guard import WriteOperationError

import weaviate


class WeaviateConnector(BaseConnector):
    name = "weaviate"
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
        self._client: Any = None

    def _connection(self) -> Any:
        if self._client is not None:
            return self._client
        if self.url.startswith("http://localhost") or self.url.startswith("http://127.0.0.1"):
            self._client = weaviate.connect_to_local()
        else:
            self._client = weaviate.connect_to_custom(http_host=self.url, http_secure=self.url.startswith("https"))
        return self._client

    def list_schemas(self) -> list[str]:
        return ["weaviate"]

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        client = self._connection()
        return [("weaviate", c) for c in client.collections.list_all()]

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        client = self._connection()
        coll = client.collections.get(name)
        config = coll.config.get()
        cols = [
            Column(name=p.name, type=str(p.data_type), nullable=True)
            for p in (config.properties or [])
        ]
        return TableSchema(schema="weaviate", name=name, columns=cols,
                           primary_key=["uuid"], foreign_keys=[], indexes=[])

    def sample_table(self, name: str, schema: str | None = None, limit: int = 10) -> QueryResult:
        coll = self._connection().collections.get(name)
        start = time.perf_counter()
        objs = coll.query.fetch_objects(limit=int(limit))
        elapsed = (time.perf_counter() - start) * 1000.0
        return self._objs_to_result(objs.objects, elapsed, truncated=False)

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        spec = self._parse_spec(sql)
        cap = max_rows if max_rows is not None else self.default_max_rows
        coll = self._connection().collections.get(spec["collection"])
        limit = int(spec.get("limit", cap))
        start = time.perf_counter()
        if "near_vector" in spec:
            res = coll.query.near_vector(near_vector=spec["near_vector"], limit=limit)
        elif "near_text" in spec:
            res = coll.query.near_text(query=spec["near_text"], limit=limit)
        else:
            res = coll.query.fetch_objects(limit=limit)
        elapsed = (time.perf_counter() - start) * 1000.0
        objs = res.objects
        truncated = len(objs) > cap
        if truncated:
            objs = objs[:cap]
        return self._objs_to_result(objs, elapsed, truncated=truncated)

    def explain(self, sql: str) -> str:
        spec = self._parse_spec(sql)
        return f"Weaviate has no EXPLAIN. Spec: collection={spec.get('collection')}"

    def _parse_spec(self, sql: str) -> dict[str, Any]:
        if not sql or not sql.strip():
            raise WriteOperationError("empty query")
        try:
            spec = json.loads(sql)
        except json.JSONDecodeError as e:
            raise WriteOperationError(f"Weaviate query must be JSON: {e}") from e
        if not isinstance(spec, dict) or "collection" not in spec:
            raise WriteOperationError("Weaviate query must include 'collection'")
        return spec

    def _objs_to_result(self, objs: list[Any], elapsed_ms: float, *, truncated: bool) -> QueryResult:
        cols: list[str] = ["uuid"]
        seen: set[str] = {"uuid"}
        norm: list[dict[str, Any]] = []
        for o in objs:
            d: dict[str, Any] = {"uuid": str(o.uuid)}
            props = getattr(o, "properties", None) or {}
            d.update(props)
            for k in props:
                if k not in seen:
                    seen.add(k)
                    cols.append(k)
            norm.append(d)
        rows = [[doc.get(c) for c in cols] for doc in norm]
        return QueryResult(columns=cols, rows=rows, row_count=len(rows),
                           truncated=truncated, elapsed_ms=elapsed_ms)

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
        self._client = None

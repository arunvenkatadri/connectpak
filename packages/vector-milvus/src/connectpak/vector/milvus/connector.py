"""Milvus connector using pymilvus (MilvusClient).

Config: a Milvus URI, e.g.
    http://localhost:19530
    https://api-key@in03-xxxxxxxxx.api.cloud.zilliz.com

Mapping:
- list_schemas() -> ["milvus"]
- list_tables() -> collections
- describe_table(name) -> field schema (vector + scalar fields)
- sample_table(name, limit) -> first `limit` rows via query
- query(sql, max_rows) -> JSON spec:
      {"collection": "x", "vector": [...], "limit": N, "filter": "...",
       "output_fields": ["id", "title"], "anns_field": "embedding"}
  or  {"collection": "x", "filter": "id > 100", "limit": N,
       "output_fields": [...]}
"""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import unquote, urlparse

from pymilvus import MilvusClient

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
    uri = f"{p.scheme or 'http'}://{netloc}"
    return {"uri": uri, "token": api_key}


class MilvusConnector(BaseConnector):
    name = "milvus"
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
        self._client: MilvusClient | None = None

    def _connection(self) -> MilvusClient:
        if self._client is not None:
            return self._client
        params = _parse_config(self.config)
        kwargs: dict[str, Any] = {"uri": params["uri"]}
        if params["token"]:
            kwargs["token"] = params["token"]
        self._client = MilvusClient(**kwargs)
        return self._client

    def list_schemas(self) -> list[str]:
        return ["milvus"]

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        return [("milvus", c) for c in self._connection().list_collections()]

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        info = self._connection().describe_collection(name)
        cols: list[Column] = []
        pk: list[str] = []
        for f in info.get("fields", []):
            ftype = str(f.get("type", "")).split(".")[-1]
            params = f.get("params") or {}
            type_str = ftype
            if "dim" in params:
                type_str = f"{ftype}(dim={params['dim']})"
            is_pk = bool(f.get("is_primary"))
            cols.append(Column(name=f["name"], type=type_str,
                               nullable=not is_pk, is_primary_key=is_pk))
            if is_pk:
                pk.append(f["name"])
        return TableSchema(schema="milvus", name=name, columns=cols,
                           primary_key=pk, foreign_keys=[], indexes=[])

    def sample_table(self, name: str, schema: str | None = None, limit: int = 10) -> QueryResult:
        client = self._connection()
        start = time.perf_counter()
        results = client.query(
            collection_name=name, filter="", limit=int(limit),
            output_fields=["*"],
        )
        elapsed = (time.perf_counter() - start) * 1000.0
        return self._docs_to_result(results, elapsed, truncated=False)

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        spec = self._parse_spec(sql)
        cap = max_rows if max_rows is not None else self.default_max_rows
        client = self._connection()
        limit = min(int(spec.get("limit", cap)), cap + 1)
        coll = spec["collection"]
        start = time.perf_counter()
        if "vector" in spec:
            kwargs = {
                "collection_name": coll, "data": [spec["vector"]],
                "limit": limit, "output_fields": spec.get("output_fields", ["*"]),
            }
            if "filter" in spec:
                kwargs["filter"] = spec["filter"]
            if "anns_field" in spec:
                kwargs["anns_field"] = spec["anns_field"]
            results_outer = client.search(**kwargs)
            results = list(results_outer[0]) if results_outer else []
            results = [dict(r) if hasattr(r, "items") else {"value": r} for r in results]
        else:
            results = client.query(
                collection_name=coll,
                filter=spec.get("filter", ""),
                limit=limit,
                output_fields=spec.get("output_fields", ["*"]),
            )
        elapsed = (time.perf_counter() - start) * 1000.0
        truncated = len(results) > cap
        if truncated:
            results = results[:cap]
        return self._docs_to_result(results, elapsed, truncated=truncated)

    def explain(self, sql: str) -> str:
        spec = self._parse_spec(sql)
        return f"Milvus has no EXPLAIN. Spec: collection={spec.get('collection')}"

    def _parse_spec(self, sql: str) -> dict[str, Any]:
        if not sql or not sql.strip():
            raise WriteOperationError("empty query")
        try:
            spec = json.loads(sql)
        except json.JSONDecodeError as e:
            raise WriteOperationError(f"Milvus query must be JSON: {e}") from e
        if not isinstance(spec, dict) or "collection" not in spec:
            raise WriteOperationError("Milvus query must include 'collection'")
        return spec

    def _docs_to_result(self, items: list[dict], elapsed_ms: float, *, truncated: bool) -> QueryResult:
        cols: list[str] = []
        seen: set[str] = set()
        for it in items:
            for k in it:
                if k not in seen:
                    seen.add(k)
                    cols.append(k)
        rows = [[it.get(c) for c in cols] for it in items]
        return QueryResult(columns=cols, rows=rows, row_count=len(rows),
                           truncated=truncated, elapsed_ms=elapsed_ms)

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
        self._client = None

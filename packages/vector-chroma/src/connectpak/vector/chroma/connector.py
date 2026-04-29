"""Chroma connector using chromadb HTTP client.

Config: a Chroma server URL, e.g.
    http://localhost:8000

Mapping:
- list_schemas() -> ["chroma"]
- list_tables() -> collections
- describe_table(name) -> a generic vector schema (Chroma is schemaless on payloads)
- sample_table(name, limit) -> first `limit` documents (no vector search)
- query(sql, max_rows) -> JSON spec:
      {"collection": "x", "query_embeddings": [[...]], "n_results": N,
       "where": {...}}  or
      {"collection": "x", "query_texts": ["..."],     "n_results": N}
"""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.parse import urlparse

import chromadb

from connectpak.core.base import (
    BaseConnector,
    Column,
    QueryResult,
    TableSchema,
)
from connectpak.core.guard import WriteOperationError


class ChromaConnector(BaseConnector):
    name = "chroma"
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
        p = urlparse(self.url)
        self._client = chromadb.HttpClient(
            host=p.hostname or "localhost",
            port=p.port or 8000,
            ssl=(p.scheme == "https"),
        )
        return self._client

    def list_schemas(self) -> list[str]:
        return ["chroma"]

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        cols = self._connection().list_collections()
        return [("chroma", getattr(c, "name", str(c))) for c in cols]

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        cols = [
            Column(name="id", type="string", nullable=False, is_primary_key=True),
            Column(name="document", type="string", nullable=True),
            Column(name="embedding", type="vector", nullable=True),
            Column(name="metadata", type="object", nullable=True),
        ]
        return TableSchema(schema="chroma", name=name, columns=cols,
                           primary_key=["id"], foreign_keys=[], indexes=[])

    def sample_table(self, name: str, schema: str | None = None, limit: int = 10) -> QueryResult:
        coll = self._connection().get_collection(name)
        start = time.perf_counter()
        result = coll.get(limit=int(limit))
        elapsed = (time.perf_counter() - start) * 1000.0
        return self._get_to_result(result, elapsed, truncated=False)

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        spec = self._parse_spec(sql)
        cap = max_rows if max_rows is not None else self.default_max_rows
        coll = self._connection().get_collection(spec["collection"])
        n = min(int(spec.get("n_results", cap)), cap + 1)
        start = time.perf_counter()
        if "query_embeddings" in spec:
            result = coll.query(query_embeddings=spec["query_embeddings"],
                                n_results=n, where=spec.get("where"))
        elif "query_texts" in spec:
            result = coll.query(query_texts=spec["query_texts"],
                                n_results=n, where=spec.get("where"))
        else:
            result = coll.get(limit=n, where=spec.get("where"))
        elapsed = (time.perf_counter() - start) * 1000.0
        if "ids" in result and isinstance(result["ids"], list) and result["ids"] and isinstance(result["ids"][0], list):
            return self._query_to_result(result, elapsed, truncated=False, cap=cap)
        return self._get_to_result(result, elapsed, truncated=False)

    def explain(self, sql: str) -> str:
        spec = self._parse_spec(sql)
        return f"Chroma has no EXPLAIN. Spec: collection={spec.get('collection')}"

    def _parse_spec(self, sql: str) -> dict[str, Any]:
        if not sql or not sql.strip():
            raise WriteOperationError("empty query")
        try:
            spec = json.loads(sql)
        except json.JSONDecodeError as e:
            raise WriteOperationError(f"Chroma query must be JSON: {e}") from e
        if not isinstance(spec, dict) or "collection" not in spec:
            raise WriteOperationError("Chroma query must include 'collection'")
        return spec

    def _get_to_result(self, result: dict[str, Any], elapsed_ms: float, *, truncated: bool) -> QueryResult:
        ids = result.get("ids", []) or []
        docs = result.get("documents", []) or [None] * len(ids)
        metas = result.get("metadatas", []) or [None] * len(ids)
        cols = ["id", "document", "metadata"]
        rows = [[ids[i], docs[i] if i < len(docs) else None,
                 metas[i] if i < len(metas) else None] for i in range(len(ids))]
        return QueryResult(columns=cols, rows=rows, row_count=len(rows),
                           truncated=truncated, elapsed_ms=elapsed_ms)

    def _query_to_result(self, result: dict[str, Any], elapsed_ms: float,
                         *, truncated: bool, cap: int) -> QueryResult:
        ids = (result.get("ids") or [[]])[0]
        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[]])[0]
        cols = ["id", "document", "distance", "metadata"]
        rows = []
        for i in range(len(ids)):
            rows.append([
                ids[i],
                docs[i] if i < len(docs) else None,
                dists[i] if i < len(dists) else None,
                metas[i] if i < len(metas) else None,
            ])
        if len(rows) > cap:
            truncated = True
            rows = rows[:cap]
        return QueryResult(columns=cols, rows=rows, row_count=len(rows),
                           truncated=truncated, elapsed_ms=elapsed_ms)

    def close(self) -> None:
        self._client = None

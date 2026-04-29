"""MongoDB connector using pymongo.

Config: a standard mongodb URI, e.g. mongodb://user:pass@host:27017/dbname

Mapping to the BaseConnector model:
- list_schemas() -> database names (excluding admin/local/config)
- list_tables(schema) -> collections in that database
- describe_table(name, schema) -> sample-based schema inference (1 doc)
- sample_table(name, schema, limit) -> first `limit` docs as rows
- query(sql, max_rows) -> `sql` is a JSON string of a find/aggregate spec:
      {"db": "x", "coll": "y", "op": "find",     "filter": {...}, "projection": {...}, "limit": N}
      {"db": "x", "coll": "y", "op": "aggregate", "pipeline": [...]}
  Read-only is enforced by accepting only `find` / `aggregate` (and
  rejecting `$out`, `$merge` stages).

`explain` runs the spec with `explain=True`.
"""

from __future__ import annotations

import json
import time
from typing import Any

import pymongo

from connectpak.core.base import (
    BaseConnector,
    Column,
    QueryResult,
    TableSchema,
)
from connectpak.core.guard import WriteOperationError

_HIDDEN_DBS = {"admin", "local", "config"}
_FORBIDDEN_AGG_STAGES = {"$out", "$merge", "$indexStats"}


def _infer_type(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "double"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    return type(v).__name__


class MongoDBConnector(BaseConnector):
    name = "mongodb"
    dialect = None

    def __init__(
        self,
        config: str,
        *,
        allow_write: bool = False,
        statement_timeout_ms: int = 30_000,
        default_max_rows: int = 1000,
    ):
        self.uri = config
        self.allow_write = allow_write
        self.statement_timeout_ms = statement_timeout_ms
        self.default_max_rows = default_max_rows
        self._client: pymongo.MongoClient | None = None

    def _connection(self) -> pymongo.MongoClient:
        if self._client is not None:
            return self._client
        self._client = pymongo.MongoClient(
            self.uri,
            socketTimeoutMS=self.statement_timeout_ms,
            serverSelectionTimeoutMS=self.statement_timeout_ms,
        )
        return self._client

    def list_schemas(self) -> list[str]:
        return sorted(
            n for n in self._connection().list_database_names() if n not in _HIDDEN_DBS
        )

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        client = self._connection()
        if schema is None:
            dbs = [d for d in client.list_database_names() if d not in _HIDDEN_DBS]
        else:
            dbs = [schema]
        out: list[tuple[str | None, str]] = []
        for d in dbs:
            for c in client[d].list_collection_names():
                out.append((d, c))
        return out

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        if schema is None:
            raise ValueError("MongoDB describe_table requires a database (schema)")
        coll = self._connection()[schema][name]
        sample = coll.find_one()
        cols: list[Column] = []
        if sample:
            for k, v in sample.items():
                cols.append(Column(name=k, type=_infer_type(v),
                                   nullable=True, is_primary_key=(k == "_id")))
        return TableSchema(schema=schema, name=name, columns=cols,
                           primary_key=["_id"] if any(c.name == "_id" for c in cols) else [],
                           foreign_keys=[], indexes=[])

    def sample_table(self, name: str, schema: str | None = None, limit: int = 10) -> QueryResult:
        if schema is None:
            raise ValueError("MongoDB sample_table requires a database (schema)")
        start = time.perf_counter()
        cursor = self._connection()[schema][name].find().limit(int(limit))
        docs = list(cursor)
        elapsed = (time.perf_counter() - start) * 1000.0
        return self._docs_to_result(docs, elapsed, truncated=False)

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        spec = self._parse_spec(sql)
        cap = max_rows if max_rows is not None else self.default_max_rows
        db = spec["db"]
        coll = self._connection()[db][spec["coll"]]
        op = spec.get("op", "find")
        start = time.perf_counter()
        if op == "find":
            cursor = coll.find(spec.get("filter", {}), spec.get("projection")).limit(cap + 1)
            docs = list(cursor)
        elif op == "aggregate":
            pipeline = spec.get("pipeline", [])
            self._guard_pipeline(pipeline)
            docs = list(coll.aggregate(pipeline + [{"$limit": cap + 1}]))
        else:
            raise WriteOperationError(f"unsupported MongoDB op: {op!r}")
        elapsed = (time.perf_counter() - start) * 1000.0
        truncated = len(docs) > cap
        if truncated:
            docs = docs[:cap]
        return self._docs_to_result(docs, elapsed, truncated=truncated)

    def _parse_spec(self, sql: str) -> dict[str, Any]:
        if not sql or not sql.strip():
            raise WriteOperationError("empty query")
        try:
            spec = json.loads(sql)
        except json.JSONDecodeError as e:
            raise WriteOperationError(f"MongoDB query must be a JSON spec: {e}") from e
        if not isinstance(spec, dict) or "db" not in spec or "coll" not in spec:
            raise WriteOperationError("MongoDB query must include 'db' and 'coll'")
        if not self.allow_write and spec.get("op", "find") not in ("find", "aggregate"):
            raise WriteOperationError(f"op {spec.get('op')!r} is not read-only")
        return spec

    def _guard_pipeline(self, pipeline: list[dict[str, Any]]) -> None:
        if self.allow_write:
            return
        for stage in pipeline:
            if not isinstance(stage, dict):
                continue
            for k in stage:
                if k in _FORBIDDEN_AGG_STAGES:
                    raise WriteOperationError(f"forbidden aggregation stage: {k}")

    def _docs_to_result(self, docs: list[dict], elapsed_ms: float, *, truncated: bool) -> QueryResult:
        cols: list[str] = []
        seen: set[str] = set()
        for d in docs:
            for k in d.keys():
                if k not in seen:
                    seen.add(k)
                    cols.append(k)
        rows = [[self._jsonable(d.get(c)) for c in cols] for d in docs]
        return QueryResult(columns=cols, rows=rows, row_count=len(rows),
                           truncated=truncated, elapsed_ms=elapsed_ms)

    @staticmethod
    def _jsonable(v: Any) -> Any:
        if isinstance(v, (str, int, float, bool, type(None))):
            return v
        return str(v)

    def explain(self, sql: str) -> str:
        spec = self._parse_spec(sql)
        coll = self._connection()[spec["db"]][spec["coll"]]
        op = spec.get("op", "find")
        if op == "find":
            cur = coll.find(spec.get("filter", {}), spec.get("projection"))
            return json.dumps(cur.explain(), default=str, indent=2)
        # aggregate explain
        pipeline = spec.get("pipeline", [])
        return json.dumps(
            self._connection()[spec["db"]].command(
                "explain", {"aggregate": spec["coll"], "pipeline": pipeline, "cursor": {}}
            ),
            default=str, indent=2,
        )

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception:
                pass
        self._client = None

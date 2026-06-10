"""ArangoDB connector using python-arango.

Config: an HTTP URL with credentials and database, e.g.
    http://root:pass@localhost:8529/_system

Mapping:
- list_schemas() -> databases visible to the user.
- list_tables(schema) -> collections in the database.
- describe_table(name, schema) -> sample-based property inference + indexes.
- query(aql, ...) -> raw AQL with a write-keyword guard.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import unquote, urlparse

from arango import ArangoClient
from connectpak.core.base import (
    BaseConnector,
    Column,
    Index,
    QueryResult,
    TableSchema,
)
from connectpak.core.guard import assert_no_write_keywords

_AQL_WRITE_KEYWORDS = ("INSERT", "UPDATE", "REPLACE", "REMOVE", "UPSERT")


def _parse_config(config: str) -> dict[str, Any]:
    p = urlparse(config)
    if p.scheme not in ("http", "https"):
        raise ValueError(f"unsupported ArangoDB scheme: {p.scheme!r}")
    netloc = p.hostname or "localhost"
    if p.port:
        netloc += f":{p.port}"
    host = f"{p.scheme}://{netloc}"
    return {
        "host": host,
        "username": unquote(p.username) if p.username else "root",
        "password": unquote(p.password) if p.password else "",
        "database": p.path.lstrip("/") or "_system",
    }


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


class ArangoDBConnector(BaseConnector):
    name = "arangodb"
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
        self._client: ArangoClient | None = None
        self._db: Any = None
        self._sys: Any = None

    def _connection(self) -> Any:
        if self._db is not None:
            return self._db
        params = _parse_config(self.config)
        self._client = ArangoClient(hosts=params["host"])
        self._sys = self._client.db(
            "_system", username=params["username"], password=params["password"]
        )
        self._db = self._client.db(
            params["database"], username=params["username"], password=params["password"]
        )
        return self._db

    def list_schemas(self) -> list[str]:
        self._connection()
        return sorted(self._sys.databases())

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        self._connection()
        if schema and schema != self._db.name:
            params = _parse_config(self.config)
            db = self._client.db(schema, username=params["username"], password=params["password"])
        else:
            db = self._db
        return sorted(
            [(db.name, c["name"]) for c in db.collections() if not c["name"].startswith("_")],
            key=lambda x: x[1],
        )

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        self._connection()
        coll = self._db.collection(name)
        sample = next(iter(coll.find({}, limit=1)), None)
        cols: list[Column] = []
        if sample:
            for k, v in sample.items():
                cols.append(Column(name=k, type=_infer_type(v),
                                   nullable=True, is_primary_key=(k == "_key")))
        idx_specs = coll.indexes() or []
        indexes = [
            Index(
                name=str(i.get("id") or i.get("name") or ""),
                columns=list(i.get("fields", [])),
                unique=bool(i.get("unique", False)),
            )
            for i in idx_specs
            if i.get("type") not in ("primary",)
        ]
        return TableSchema(schema=self._db.name, name=name, columns=cols,
                           primary_key=["_key"] if any(c.name == "_key" for c in cols) else [],
                           foreign_keys=[], indexes=indexes)

    def sample_table(self, name: str, schema: str | None = None, limit: int = 10) -> QueryResult:
        self._connection()
        start = time.perf_counter()
        cursor = self._db.aql.execute(
            "FOR doc IN @@coll LIMIT @limit RETURN doc",
            bind_vars={"@coll": name, "limit": int(limit)},
        )
        docs = list(cursor)
        elapsed = (time.perf_counter() - start) * 1000.0
        return self._docs_to_result(docs, elapsed, truncated=False)

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        if not self.allow_write:
            assert_no_write_keywords(sql, _AQL_WRITE_KEYWORDS)
        cap = max_rows if max_rows is not None else self.default_max_rows
        self._connection()
        start = time.perf_counter()
        cursor = self._db.aql.execute(sql, batch_size=min(cap + 1, 1000))
        docs: list[Any] = []
        for d in cursor:
            docs.append(d)
            if len(docs) >= cap + 1:
                break
        elapsed = (time.perf_counter() - start) * 1000.0
        truncated = len(docs) > cap
        if truncated:
            docs = docs[:cap]
        return self._docs_to_result(docs, elapsed, truncated=truncated)

    def explain(self, sql: str) -> str:
        self._connection()
        plan = self._db.aql.explain(sql)
        return str(plan)

    def _docs_to_result(self, docs: list[Any], elapsed_ms: float, *, truncated: bool) -> QueryResult:
        cols: list[str] = []
        seen: set[str] = set()
        dict_docs: list[dict] = []
        for d in docs:
            if isinstance(d, dict):
                dict_docs.append(d)
                for k in d:
                    if k not in seen:
                        seen.add(k)
                        cols.append(k)
            else:
                dict_docs.append({"value": d})
                if "value" not in seen:
                    seen.add("value")
                    cols.append("value")
        rows = [[doc.get(c) for c in cols] for doc in dict_docs]
        return QueryResult(columns=cols, rows=rows, row_count=len(rows),
                           truncated=truncated, elapsed_ms=elapsed_ms)

    def close(self) -> None:
        # python-arango sessions don't need explicit closing.
        self._db = None
        self._sys = None
        self._client = None

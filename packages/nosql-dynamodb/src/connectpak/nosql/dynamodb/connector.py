"""DynamoDB connector using boto3.

Config: an AWS region name (auth via standard boto3 credential chain).

Mapping:
- list_schemas() -> [region] (DynamoDB has no schema concept)
- list_tables() -> all tables in the region
- describe_table(name) -> AttributeDefinitions + KeySchema (PK/SK as PK)
- sample_table(name, limit) -> Scan with Limit
- query(sql, max_rows) -> JSON spec:
      {"op": "scan",     "table": "x", "filter": {...}, "limit": N}
      {"op": "query",    "table": "x", "key_condition": {...}, "limit": N}
      {"op": "get_item", "table": "x", "key": {"pk": "..."}}
  Or PartiQL:
      {"op": "execute_statement", "statement": "SELECT * FROM ..."}
  with a parser-guard check.

Read-only is enforced by accepting only `scan`, `query`, `get_item`, and
`execute_statement` (PartiQL with parser guard).
"""

from __future__ import annotations

import json
import time
from typing import Any

import boto3

from connectpak.core.base import (
    BaseConnector,
    Column,
    QueryResult,
    TableSchema,
)
from connectpak.core.guard import WriteOperationError, assert_read_only

_READ_OPS = {"scan", "query", "get_item", "execute_statement"}


class DynamoDBConnector(BaseConnector):
    name = "dynamodb"
    dialect = None

    def __init__(
        self,
        config: str,
        *,
        allow_write: bool = False,
        statement_timeout_ms: int = 30_000,
        default_max_rows: int = 1000,
    ):
        self.region = config
        self.allow_write = allow_write
        self.statement_timeout_ms = statement_timeout_ms
        self.default_max_rows = default_max_rows
        self._client: Any = None

    def _connection(self) -> Any:
        if self._client is not None:
            return self._client
        self._client = boto3.client("dynamodb", region_name=self.region)
        return self._client

    def list_schemas(self) -> list[str]:
        return [self.region]

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        out: list[tuple[str | None, str]] = []
        last: str | None = None
        client = self._connection()
        while True:
            kwargs: dict[str, Any] = {}
            if last:
                kwargs["ExclusiveStartTableName"] = last
            resp = client.list_tables(**kwargs)
            for t in resp.get("TableNames", []):
                out.append((self.region, t))
            last = resp.get("LastEvaluatedTableName")
            if not last:
                break
        return out

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        desc = self._connection().describe_table(TableName=name)["Table"]
        attrs = {a["AttributeName"]: a["AttributeType"] for a in desc.get("AttributeDefinitions", [])}
        key_cols = [k["AttributeName"] for k in desc.get("KeySchema", [])]
        cols = [
            Column(name=k, type=v, nullable=False, is_primary_key=(k in key_cols))
            for k, v in attrs.items()
        ]
        return TableSchema(schema=self.region, name=name, columns=cols,
                           primary_key=key_cols, foreign_keys=[], indexes=[])

    def sample_table(self, name: str, schema: str | None = None, limit: int = 10) -> QueryResult:
        start = time.perf_counter()
        resp = self._connection().scan(TableName=name, Limit=int(limit))
        elapsed = (time.perf_counter() - start) * 1000.0
        items = [self._unmarshal(it) for it in resp.get("Items", [])]
        return self._items_to_result(items, elapsed, truncated=False)

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        spec = self._parse_spec(sql)
        cap = max_rows if max_rows is not None else self.default_max_rows
        op = spec["op"]
        client = self._connection()
        start = time.perf_counter()
        if op == "scan":
            resp = client.scan(TableName=spec["table"], Limit=cap + 1)
            items = [self._unmarshal(i) for i in resp.get("Items", [])]
        elif op == "query":
            kwargs = {k: v for k, v in spec.items() if k not in ("op",)}
            kwargs["Limit"] = cap + 1
            resp = client.query(**kwargs)
            items = [self._unmarshal(i) for i in resp.get("Items", [])]
        elif op == "get_item":
            resp = client.get_item(TableName=spec["table"], Key=self._marshal(spec["key"]))
            items = [self._unmarshal(resp["Item"])] if resp.get("Item") else []
        elif op == "execute_statement":
            stmt = spec["statement"]
            if not self.allow_write:
                assert_read_only(stmt, dialect=None)
            resp = client.execute_statement(Statement=stmt, Limit=cap + 1)
            items = [self._unmarshal(i) for i in resp.get("Items", [])]
        else:
            raise WriteOperationError(f"unsupported DynamoDB op: {op!r}")
        elapsed = (time.perf_counter() - start) * 1000.0
        truncated = len(items) > cap
        if truncated:
            items = items[:cap]
        return self._items_to_result(items, elapsed, truncated=truncated)

    def explain(self, sql: str) -> str:
        spec = self._parse_spec(sql)
        return f"DynamoDB does not provide EXPLAIN. Spec accepted: op={spec.get('op')}, table={spec.get('table')}"

    def _parse_spec(self, sql: str) -> dict[str, Any]:
        if not sql or not sql.strip():
            raise WriteOperationError("empty query")
        try:
            spec = json.loads(sql)
        except json.JSONDecodeError as e:
            raise WriteOperationError(f"DynamoDB query must be a JSON spec: {e}") from e
        if not isinstance(spec, dict) or "op" not in spec:
            raise WriteOperationError("DynamoDB query must include 'op'")
        if not self.allow_write and spec["op"] not in _READ_OPS:
            raise WriteOperationError(f"op {spec['op']!r} is not read-only")
        return spec

    def _items_to_result(self, items: list[dict], elapsed_ms: float, *, truncated: bool) -> QueryResult:
        cols: list[str] = []
        seen: set[str] = set()
        for it in items:
            for k in it:
                if k not in seen:
                    seen.add(k)
                    cols.append(k)
        rows = [[self._jsonable(it.get(c)) for c in cols] for it in items]
        return QueryResult(columns=cols, rows=rows, row_count=len(rows),
                           truncated=truncated, elapsed_ms=elapsed_ms)

    @staticmethod
    def _jsonable(v: Any) -> Any:
        if isinstance(v, (str, int, float, bool, type(None))):
            return v
        if isinstance(v, (list, dict)):
            return v
        return str(v)

    @staticmethod
    def _marshal(d: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in d.items():
            if isinstance(v, str):
                out[k] = {"S": v}
            elif isinstance(v, bool):
                out[k] = {"BOOL": v}
            elif isinstance(v, (int, float)):
                out[k] = {"N": str(v)}
            elif v is None:
                out[k] = {"NULL": True}
            else:
                out[k] = {"S": str(v)}
        return out

    @staticmethod
    def _unmarshal(item: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for k, v in item.items():
            if "S" in v:
                out[k] = v["S"]
            elif "N" in v:
                try:
                    out[k] = int(v["N"]) if "." not in v["N"] else float(v["N"])
                except ValueError:
                    out[k] = v["N"]
            elif "BOOL" in v:
                out[k] = v["BOOL"]
            elif "NULL" in v:
                out[k] = None
            elif "L" in v:
                out[k] = [DynamoDBConnector._unmarshal({"_": x})["_"] for x in v["L"]]
            elif "M" in v:
                out[k] = DynamoDBConnector._unmarshal(v["M"])
            else:
                out[k] = v
        return out

    def close(self) -> None:
        self._client = None

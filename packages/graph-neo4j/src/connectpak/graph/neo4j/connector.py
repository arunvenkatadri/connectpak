"""Neo4j connector using the official `neo4j` driver (Bolt).

Config: a Bolt URI with credentials, e.g.
    bolt://neo4j:password@localhost:7687
    neo4j+s://user:pass@cluster.example.com

Mapping:
- list_schemas() -> ["nodes", "relationships"]
- list_tables(schema) -> node labels (schema=nodes) or relationship types
                        (schema=relationships).
- describe_table(name, schema) -> property keys and (for nodes) the
                                  constraints / indexes touching them.
- sample_table(name, schema, limit) -> matches against the label/type.
- query(cypher, max_rows) -> raw Cypher executed via session.execute_read,
                             which the driver routes to a read-only replica
                             where available. Cypher is also screened with
                             a write-keyword guard.
"""

from __future__ import annotations

import time
from typing import Any
from urllib.parse import unquote, urlparse

from connectpak.core.base import (
    BaseConnector,
    Column,
    Index,
    QueryResult,
    TableSchema,
)
from connectpak.core.guard import assert_no_write_keywords

from neo4j import GraphDatabase

_CYPHER_WRITE_KEYWORDS = (
    "CREATE", "MERGE", "DELETE", "REMOVE", "SET", "DROP", "DETACH",
    "FOREACH", "LOAD",
)


def _parse_config(config: str) -> dict[str, Any]:
    p = urlparse(config)
    auth = None
    if p.username:
        auth = (unquote(p.username), unquote(p.password or ""))
    netloc = p.hostname or "localhost"
    if p.port:
        netloc += f":{p.port}"
    uri = f"{p.scheme or 'bolt'}://{netloc}"
    return {"uri": uri, "auth": auth}


class Neo4jConnector(BaseConnector):
    name = "neo4j"
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
        self._driver: Any = None

    def _connection(self) -> Any:
        if self._driver is not None:
            return self._driver
        params = _parse_config(self.config)
        self._driver = GraphDatabase.driver(
            params["uri"],
            auth=params["auth"],
            connection_timeout=self.statement_timeout_ms / 1000.0,
        )
        return self._driver

    def _session(self):
        return self._connection().session()

    def list_schemas(self) -> list[str]:
        return ["nodes", "relationships"]

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        out: list[tuple[str | None, str]] = []
        with self._session() as s:
            if schema in (None, "nodes"):
                res = s.run("CALL db.labels() YIELD label RETURN label ORDER BY label")
                out.extend(("nodes", r["label"]) for r in res)
            if schema in (None, "relationships"):
                res = s.run(
                    "CALL db.relationshipTypes() YIELD relationshipType "
                    "RETURN relationshipType ORDER BY relationshipType"
                )
                out.extend(("relationships", r["relationshipType"]) for r in res)
        return out

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        schema = schema or "nodes"
        cols: list[Column] = []
        with self._session() as s:
            if schema == "nodes":
                res = s.run(
                    "CALL db.schema.nodeTypeProperties() "
                    "YIELD nodeLabels, propertyName, propertyTypes, mandatory "
                    "WHERE $label IN nodeLabels "
                    "RETURN propertyName, propertyTypes, mandatory",
                    label=name,
                )
            else:
                res = s.run(
                    "CALL db.schema.relTypeProperties() "
                    "YIELD relType, propertyName, propertyTypes, mandatory "
                    "WHERE relType = ':`' + $rel + '`' "
                    "RETURN propertyName, propertyTypes, mandatory",
                    rel=name,
                )
            for r in res:
                if r["propertyName"] is None:
                    continue
                t = ",".join(r["propertyTypes"]) if r["propertyTypes"] else "any"
                cols.append(Column(
                    name=r["propertyName"], type=t, nullable=not bool(r["mandatory"]),
                ))

            indexes: list[Index] = []
            if schema == "nodes":
                idx_res = s.run("SHOW INDEXES YIELD name, labelsOrTypes, properties, type")
                for r in idx_res:
                    if r["labelsOrTypes"] and name in r["labelsOrTypes"]:
                        indexes.append(Index(
                            name=r["name"], columns=list(r["properties"] or []),
                            unique=("UNIQUE" in (r["type"] or "").upper()),
                        ))

        return TableSchema(schema=schema, name=name, columns=cols,
                           primary_key=[], foreign_keys=[], indexes=indexes)

    def sample_table(self, name: str, schema: str | None = None, limit: int = 10) -> QueryResult:
        schema = schema or "nodes"
        if schema == "nodes":
            cypher = f"MATCH (n:`{name}`) RETURN n LIMIT {int(limit)}"
        else:
            cypher = (
                f"MATCH (a)-[r:`{name}`]->(b) "
                f"RETURN a, r, b LIMIT {int(limit)}"
            )
        return self._run(cypher, max_rows=limit)

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        if not self.allow_write:
            assert_no_write_keywords(sql, _CYPHER_WRITE_KEYWORDS)
        return self._run(sql, max_rows=max_rows)

    def explain(self, sql: str) -> str:
        with self._session() as s:
            res = s.run("EXPLAIN " + sql)
            summary = res.consume()
            plan = summary.plan
            return str(plan) if plan is not None else "(no plan available)"

    def _run(self, cypher: str, max_rows: int | None = None) -> QueryResult:
        cap = max_rows if max_rows is not None else self.default_max_rows
        start = time.perf_counter()
        with self._session() as s:
            if not self.allow_write:
                rows_data = s.execute_read(self._fetch, cypher, cap + 1)
            else:
                rows_data = s.execute_write(self._fetch, cypher, cap + 1)
        elapsed = (time.perf_counter() - start) * 1000.0
        cols, rows = rows_data
        truncated = len(rows) > cap
        if truncated:
            rows = rows[:cap]
        return QueryResult(columns=cols, rows=rows, row_count=len(rows),
                           truncated=truncated, elapsed_ms=elapsed)

    @staticmethod
    def _fetch(tx, cypher: str, fetch_n: int) -> tuple[list[str], list[list[Any]]]:
        result = tx.run(cypher)
        keys = list(result.keys())
        rows: list[list[Any]] = []
        for record in result:
            rows.append([Neo4jConnector._jsonable(record[k]) for k in keys])
            if len(rows) >= fetch_n:
                break
        return keys, rows

    @staticmethod
    def _jsonable(v: Any) -> Any:
        if isinstance(v, (str, int, float, bool, type(None))):
            return v
        if hasattr(v, "items"):
            return {k: Neo4jConnector._jsonable(val) for k, val in v.items()}
        if isinstance(v, (list, tuple)):
            return [Neo4jConnector._jsonable(x) for x in v]
        return str(v)

    def close(self) -> None:
        if self._driver is not None:
            try:
                self._driver.close()
            except Exception:
                pass
        self._driver = None

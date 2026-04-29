"""Neo4j connector — stub.

Every method raises NotImplementedError. Implement against the contract
defined in `connectpak.core.base.BaseConnector` and keep the safety
contract intact: parser guard + engine-level read-only + statement timeout
+ row cap.
"""

from __future__ import annotations

from connectpak.core.base import BaseConnector, QueryResult, TableSchema


class Neo4jConnector(BaseConnector):
    name = "neo4j"
    dialect = None

    def list_schemas(self) -> list[str]:
        raise NotImplementedError("Neo4j connector is not yet implemented")

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        raise NotImplementedError("Neo4j connector is not yet implemented")

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        raise NotImplementedError("Neo4j connector is not yet implemented")

    def sample_table(
        self, name: str, schema: str | None = None, limit: int = 10
    ) -> QueryResult:
        raise NotImplementedError("Neo4j connector is not yet implemented")

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        raise NotImplementedError("Neo4j connector is not yet implemented")

    def explain(self, sql: str) -> str:
        raise NotImplementedError("Neo4j connector is not yet implemented")

    def close(self) -> None:
        return None

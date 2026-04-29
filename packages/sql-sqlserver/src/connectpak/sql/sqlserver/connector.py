"""SQL Server connector — stub.

Every method raises NotImplementedError. Implement against the contract
defined in `connectpak.core.base.BaseConnector` and keep the safety
contract intact: parser guard + engine-level read-only + statement timeout
+ row cap.
"""

from __future__ import annotations

from connectpak.core.base import BaseConnector, QueryResult, TableSchema


class SQLServerConnector(BaseConnector):
    name = "sqlserver"
    dialect = 'tsql'

    def list_schemas(self) -> list[str]:
        raise NotImplementedError("SQL Server connector is not yet implemented")

    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]:
        raise NotImplementedError("SQL Server connector is not yet implemented")

    def describe_table(self, name: str, schema: str | None = None) -> TableSchema:
        raise NotImplementedError("SQL Server connector is not yet implemented")

    def sample_table(
        self, name: str, schema: str | None = None, limit: int = 10
    ) -> QueryResult:
        raise NotImplementedError("SQL Server connector is not yet implemented")

    def query(self, sql: str, max_rows: int | None = None) -> QueryResult:
        raise NotImplementedError("SQL Server connector is not yet implemented")

    def explain(self, sql: str) -> str:
        raise NotImplementedError("SQL Server connector is not yet implemented")

    def close(self) -> None:
        return None

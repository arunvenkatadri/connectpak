"""BaseConnector contract and shared dataclasses."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Column:
    name: str
    type: str
    nullable: bool
    default: str | None = None
    is_primary_key: bool = False
    comment: str | None = None


@dataclass
class ForeignKey:
    columns: list[str]
    referenced_schema: str | None
    referenced_table: str
    referenced_columns: list[str]
    name: str | None = None


@dataclass
class Index:
    name: str
    columns: list[str]
    unique: bool = False


@dataclass
class TableSchema:
    schema: str | None
    name: str
    columns: list[Column]
    primary_key: list[str] = field(default_factory=list)
    foreign_keys: list[ForeignKey] = field(default_factory=list)
    indexes: list[Index] = field(default_factory=list)
    comment: str | None = None


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    truncated: bool = False
    elapsed_ms: float | None = None


class BaseConnector(ABC):
    """Abstract base class every engine connector implements.

    Subclasses MUST keep the safety contract intact:
    parser guard + engine-level read-only + statement timeout + row cap.
    """

    name: str = "base"
    dialect: str | None = None
    allow_write: bool = False
    statement_timeout_ms: int = 30_000
    default_max_rows: int = 1000

    @abstractmethod
    def list_schemas(self) -> list[str]: ...

    @abstractmethod
    def list_tables(self, schema: str | None = None) -> list[tuple[str | None, str]]: ...

    @abstractmethod
    def describe_table(self, name: str, schema: str | None = None) -> TableSchema: ...

    @abstractmethod
    def sample_table(
        self, name: str, schema: str | None = None, limit: int = 10
    ) -> QueryResult: ...

    @abstractmethod
    def query(self, sql: str, max_rows: int | None = None) -> QueryResult: ...

    @abstractmethod
    def explain(self, sql: str) -> str: ...

    @abstractmethod
    def close(self) -> None: ...

"""Core BaseConnector, read-only guard, and MCP server runner."""

from connectpak.core.base import (
    BaseConnector,
    Column,
    ForeignKey,
    Index,
    QueryResult,
    TableSchema,
)
from connectpak.core.guard import WriteOperationError, assert_read_only
from connectpak.core.server import build_server, serve

__all__ = [
    "BaseConnector",
    "Column",
    "ForeignKey",
    "Index",
    "QueryResult",
    "TableSchema",
    "WriteOperationError",
    "assert_read_only",
    "build_server",
    "serve",
]

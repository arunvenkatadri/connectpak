"""Read-only SQL guard.

Blocks state-mutating statements before they reach the engine. This is the
first of two layers — the engine-level read-only mode is the second. Both
must remain intact.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp


class WriteOperationError(ValueError):
    """Raised when SQL contains any state-mutating operation."""


_ALLOWED_TOP_LEVEL: tuple[type[exp.Expression], ...] = (
    exp.Select,
    exp.Union,
    exp.Intersect,
    exp.Except,
    exp.Subquery,
    exp.With,
    exp.Describe,
    exp.Show,
    exp.Pragma,
)

_FORBIDDEN: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Create,
    exp.Drop,
    exp.Alter,
    exp.TruncateTable,
    exp.Command,
)


def assert_read_only(sql: str, dialect: str | None = None) -> None:
    """Raise WriteOperationError if the SQL would change state.

    - Empty / whitespace-only SQL is rejected.
    - Each parsed top-level statement must be one of the allowed read shapes.
    - The full AST is walked; any forbidden node anywhere triggers a reject.
      This catches "WITH x AS (DELETE ...) SELECT ..." style attacks.
    """
    if sql is None or not sql.strip():
        raise WriteOperationError("empty SQL")

    try:
        parsed = sqlglot.parse(sql, dialect=dialect)
    except Exception as e:
        raise WriteOperationError(f"could not parse SQL: {e}") from e

    if not parsed:
        raise WriteOperationError("empty SQL")

    for stmt in parsed:
        if stmt is None:
            raise WriteOperationError("empty statement")

        if not isinstance(stmt, _ALLOWED_TOP_LEVEL):
            raise WriteOperationError(
                f"top-level statement {type(stmt).__name__} is not read-only"
            )

        for node in stmt.walk():
            target = node[0] if isinstance(node, tuple) else node
            if isinstance(target, _FORBIDDEN):
                raise WriteOperationError(
                    f"forbidden operation found in SQL: {type(target).__name__}"
                )

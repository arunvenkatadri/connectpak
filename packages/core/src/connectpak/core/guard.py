"""Read-only query guards.

Blocks state-mutating statements before they reach the engine. This is the
first of two layers — the engine-level read-only mode is the second. Both
must remain intact.
"""

from __future__ import annotations

import re

import sqlglot
from sqlglot import exp


class WriteOperationError(ValueError):
    """Raised when a query contains any state-mutating operation."""


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
    # `SELECT ... INTO new_table` creates a table (T-SQL / Postgres): a write
    # hiding inside an otherwise-allowed Select. exp.Into also covers the
    # nested-subquery form because we walk the whole tree.
    exp.Into,
    # `SELECT ... FOR UPDATE` / `FOR SHARE` acquires row locks — write intent,
    # and it can block other transactions. Not read-only.
    exp.Lock,
)

# SQLite table-valued informational pragmas. sqlglot's sqlite dialect parses
# both `PRAGMA table_info(users)` and the mutating `PRAGMA journal_mode=WAL`
# as an EQ node, so we cannot tell an argument-taking read pragma from a
# setter structurally. These names are always reads regardless of form; any
# other pragma carrying an assignment (`name = value`) is treated as a setter
# and rejected.
_READ_PRAGMAS: frozenset[str] = frozenset(
    {
        "table_info",
        "table_xinfo",
        "table_list",
        "index_info",
        "index_xinfo",
        "index_list",
        "foreign_key_list",
        "foreign_key_check",
        "collation_list",
        "database_list",
        "function_list",
        "module_list",
        "pragma_list",
        "compile_options",
        "integrity_check",
        "quick_check",
        "freelist_count",
        "page_count",
        "data_version",
    }
)


def _reject_mutating_pragma(pragma: exp.Pragma) -> None:
    """Reject a PRAGMA that assigns a value (a setter), allow read forms.

    Read forms are: a bare name (`PRAGMA user_version`) or a table-valued
    informational pragma (`PRAGMA table_info(users)`). A setter such as
    `PRAGMA journal_mode = WAL` or `PRAGMA user_version = 5` mutates and is
    rejected.
    """
    inner = pragma.this
    if not isinstance(inner, exp.EQ):
        return  # bare name → read form
    name_node = inner.this
    name = (name_node.name if hasattr(name_node, "name") else str(name_node)).lower()
    if name not in _READ_PRAGMAS:
        raise WriteOperationError(f"mutating PRAGMA is not read-only: {name}")


def assert_read_only(sql: str, dialect: str | None = None) -> None:
    """Raise WriteOperationError if the SQL would change state.

    - Empty / whitespace-only SQL is rejected.
    - Each parsed top-level statement must be one of the allowed read shapes.
    - The full AST is walked; any forbidden node anywhere triggers a reject.
      This catches "WITH x AS (DELETE ...) SELECT ..." style attacks, as well
      as `SELECT ... INTO`, `FOR UPDATE` locks, and mutating PRAGMA setters.
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

        if isinstance(stmt, exp.Pragma):
            _reject_mutating_pragma(stmt)

        for node in stmt.walk():
            target = node[0] if isinstance(node, tuple) else node
            if isinstance(target, _FORBIDDEN):
                raise WriteOperationError(
                    f"forbidden operation found in SQL: {type(target).__name__}"
                )


def assert_no_write_keywords(text: str, keywords: tuple[str, ...]) -> None:
    """Lightweight write-keyword check for query languages outside SQL.

    Less robust than `assert_read_only`'s full AST walk: a keyword inside a
    string literal can produce a false positive. Used for Cypher / CQL /
    AQL / Gremlin where sqlglot does not provide a parser.
    """
    if text is None or not text.strip():
        raise WriteOperationError("empty query")
    for kw in keywords:
        if re.search(rf"\b{re.escape(kw)}\b", text, re.IGNORECASE):
            raise WriteOperationError(f"forbidden keyword in query: {kw}")

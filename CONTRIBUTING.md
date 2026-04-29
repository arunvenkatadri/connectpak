# Contributing

Thanks for considering a contribution. The most useful thing you can do is
turn a stub package into a full implementation.

## The contract

Every connector subclasses `connectpak.core.base.BaseConnector` and
implements six methods:

| Method            | Returns                                |
| ----------------- | -------------------------------------- |
| `list_schemas`    | `list[str]`                            |
| `list_tables`     | `list[tuple[str \| None, str]]`        |
| `describe_table`  | `TableSchema`                          |
| `sample_table`    | `QueryResult`                          |
| `query`           | `QueryResult`                          |
| `explain`         | `str`                                  |
| `close`           | `None`                                 |

Plus the class attributes `name`, `dialect`, `allow_write`,
`statement_timeout_ms`, `default_max_rows`.

The smallest end-to-end example is `packages/sql-sqlite` — start there.

## Safety requirements (non-negotiable)

A connector PR will not be merged unless all four are present:

1. **Parser guard.** Call `assert_read_only(sql, dialect=self.dialect)` from
   `query` whenever `self.allow_write` is false.
2. **Engine-level read-only.** Configure the underlying driver to refuse
   writes (Postgres `default_transaction_read_only=on`, SQLite `mode=ro` URI,
   etc.). The parser guard alone is not enough.
3. **Statement timeout.** Wire `statement_timeout_ms` to whatever the engine
   exposes.
4. **Row cap.** Fetch `max_rows + 1` and set `truncated=True` if the extra
   row showed up.

## Layout

PEP 420 namespace packages, one package per engine, one `pyproject.toml`
each. Use the existing packages as templates. The wheel must declare
`[tool.hatch.build.targets.wheel] packages = ["src/connectpak"]`.

## Tests

Use `packages/core/tests/test_guard.py` and
`packages/sql-sqlite/tests/test_connector.py` as the model. At minimum, your
PR should cover:

- `list_schemas`, `list_tables`, `describe_table` (cols / PK / FK / index).
- `sample_table`, `query`, query truncation.
- Guard rejection of a write statement.
- Engine-level rejection (a direct write on the read-only connection raises).

Run the suite with:

```bash
uv sync
uv run pytest
```

## Style

`ruff check` should pass. Keep public APIs typed.

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

1. **Query guard.** For SQL engines call `assert_read_only(sql,
   dialect=self.dialect)` from `query` whenever `self.allow_write` is false.
   For non-SQL engines either whitelist read operations in the JSON spec or
   call `assert_no_write_keywords(text, keywords)` with the language's write
   keywords. Any identifier you interpolate into a query string (e.g. in
   `sample_table`) must be quoted with engine-specific escaping or
   parameterized — never an unescaped f-string.
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

## Engine registry and plugin

`packages/connectpak/src/connectpak/launcher/engines.py` lists every engine:
its package, connection env var, URL schemes, and example. The `connectpak`
launcher and the plugin generator both read it. When you add an engine:

1. Add it to `ENGINES` in that file.
2. Add the package to `dependencies` in `packages/connectpak/pyproject.toml`,
   pinned to the release version.
3. Regenerate the plugin.

`plugins/` and both marketplace files (`.claude-plugin/marketplace.json`,
`.agents/plugins/marketplace.json`) are generated. Don't edit them by hand:

```bash
uv run python scripts/gen_plugins.py          # write
uv run python scripts/gen_plugins.py --check  # what CI runs
```

`packages/connectpak/tests` fails if the registry and the packages disagree.
To try the plugin against unpushed changes, commit them and generate with
`--source "file://$PWD" --ref <your-branch>` (don't commit that output).
Then add the repo as a local marketplace in either host.

## Releasing

All packages share one version. Bump `version` in every `pyproject.toml`
and the pins in `packages/connectpak/pyproject.toml`, regenerate the plugin
(it pins `connectpak==<version>`), merge, then push a `v<version>` tag. The
Release workflow tests, builds, and publishes every package to PyPI.

## Style

`ruff check` should pass. Keep public APIs typed.

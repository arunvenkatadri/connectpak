# connectpak-sql-sqlite

SQLite connector for connectpak. Uses Python's stdlib `sqlite3`, no external
deps.

## Quick start

```bash
uv sync
export CONNECTPAK_SQLITE_PATH="/path/to/db.sqlite"
uv run connectpak-sql-sqlite
```

By default the database is opened in `mode=ro` URI mode (engine-level read
only) on top of the parser guard from `connectpak-core`. Pass
`--allow-write` only if you really mean it. `:memory:` databases are always
writable.

This package is also the reference / smoke-test target — start here when
implementing a new engine.

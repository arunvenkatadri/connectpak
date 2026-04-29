# connectpak-sql-postgres

Postgres connector for connectpak. Uses [psycopg 3](https://www.psycopg.org/).

## Quick start

```bash
uv sync
export CONNECTPAK_POSTGRES_DSN="postgresql://user:pass@localhost:5432/mydb"
uv run connectpak-sql-postgres
```

By default the connection is opened with `default_transaction_read_only=on`
and a session-level read-only characteristic. Combined with the parser guard
in `connectpak-core`, this gives two independent layers of write protection.

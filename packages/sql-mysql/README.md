# connectpak-sql-mysql

MySQL connector for connectpak. Uses [PyMySQL](https://pymysql.readthedocs.io/).

## Quick start

```bash
uv sync
export CONNECTPAK_MYSQL_DSN="mysql://user:pass@localhost:3306/mydb"
uv run connectpak-sql-mysql
```

The connection issues `SET SESSION TRANSACTION READ ONLY` and
`SET SESSION MAX_EXECUTION_TIME = N` (with autocommit on) so all statements
in the session are read-only and timeout-bounded. Combined with the parser
guard in `connectpak-core`, this is the standard two-layer defense.

In MySQL "schema" and "database" are synonyms — `list_schemas()` returns
databases, `list_tables(schema=...)` lists tables in that database.

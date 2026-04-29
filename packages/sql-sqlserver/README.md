# connectpak-sql-sqlserver

SQL Server connector for connectpak. Uses
[pymssql](https://www.pymssql.org/).

## Quick start

```bash
uv sync
export CONNECTPAK_SQLSERVER_DSN="mssql://user:pass@host:1433/mydb"
uv run connectpak-sql-sqlserver
```

SQL Server has no clean session-level "read-only" toggle, so the primary
write protection here is the parser guard plus a per-cursor query timeout.
For production deployments, point the DSN at a database user that only has
`db_datareader`-class permissions.

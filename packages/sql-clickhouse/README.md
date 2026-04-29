# connectpak-sql-clickhouse

ClickHouse connector for connectpak. Uses
[clickhouse-connect](https://github.com/ClickHouse/clickhouse-connect)
(HTTP interface, default port 8123).

## Quick start

```bash
uv sync
export CONNECTPAK_CLICKHOUSE_DSN="clickhouse://default:@localhost:8123/default"
uv run connectpak-sql-clickhouse
```

The client is opened with `readonly=1` (engine-level write block) and
`max_execution_time` set from `--statement-timeout-ms`. The parser guard in
`connectpak-core` is the second layer.

ClickHouse has no foreign keys; `describe_table` returns indexes from
`system.data_skipping_indices` and the primary-key columns from
`system.columns.is_in_primary_key`.

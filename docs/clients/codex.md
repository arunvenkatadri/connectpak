# Using connectpak with Codex

Each engine is a Codex plugin in the `connectpak` marketplace.

## Install

```bash
codex plugin marketplace add arunvenkatadri/connectpak
codex plugin add connectpak-postgres@connectpak
```

Or browse the marketplace with `/plugins` inside Codex.

## Configure

Codex plugins don't prompt for settings. The server reads the engine's
connection string from your environment instead, so export it before you
start Codex:

```bash
export CONNECTPAK_POSTGRES_DSN="postgresql://reader:pw@localhost:5432/app"
codex
```

Codex doesn't pass your whole environment to MCP servers. Each plugin
forwards only the variables it declares (`env_vars` in its
`codex.mcp.json`).

| Plugin | Variable |
| --- | --- |
| connectpak-postgres | `CONNECTPAK_POSTGRES_DSN` |
| connectpak-sqlite | `CONNECTPAK_SQLITE_PATH` |
| connectpak-mysql | `CONNECTPAK_MYSQL_DSN` |
| connectpak-clickhouse | `CONNECTPAK_CLICKHOUSE_DSN` |
| connectpak-sqlserver | `CONNECTPAK_SQLSERVER_DSN` |
| connectpak-oracle | `CONNECTPAK_ORACLE_DSN` |
| connectpak-bigquery | `CONNECTPAK_BIGQUERY_PROJECT` (+ `GOOGLE_APPLICATION_CREDENTIALS`, `GOOGLE_CLOUD_PROJECT`, `CLOUDSDK_CONFIG`) |
| connectpak-snowflake | `CONNECTPAK_SNOWFLAKE_DSN` |
| connectpak-redshift | `CONNECTPAK_REDSHIFT_DSN` |
| connectpak-databricks | `CONNECTPAK_DATABRICKS_DSN` |
| connectpak-mongodb | `CONNECTPAK_MONGODB_URI` |
| connectpak-dynamodb | `CONNECTPAK_DYNAMODB_REGION` (+ `AWS_PROFILE`, `AWS_REGION`, access keys, config file paths) |
| connectpak-elasticsearch | `CONNECTPAK_ELASTICSEARCH_URL` |
| connectpak-cassandra | `CONNECTPAK_CASSANDRA_HOSTS` |
| connectpak-neo4j | `CONNECTPAK_NEO4J_URI` |
| connectpak-memgraph | `CONNECTPAK_MEMGRAPH_URI` |
| connectpak-arangodb | `CONNECTPAK_ARANGODB_URL` |
| connectpak-neptune | `CONNECTPAK_NEPTUNE_URL` |
| connectpak-pgvector | `CONNECTPAK_PGVECTOR_DSN` |
| connectpak-pinecone | `CONNECTPAK_PINECONE_API_KEY` |
| connectpak-weaviate | `CONNECTPAK_WEAVIATE_URL` |
| connectpak-qdrant | `CONNECTPAK_QDRANT_URL` |
| connectpak-chroma | `CONNECTPAK_CHROMA_URL` |
| connectpak-milvus | `CONNECTPAK_MILVUS_URI` |

The server starts with `uvx`, so [uv](https://docs.astral.sh/uv/) must be on
your `PATH`. The first launch downloads the connector and its driver.

## What you get

- An MCP server named after the engine (for example `postgres`) with the six
  connectpak tools: `list_schemas`, `list_tables`, `describe_table`,
  `sample_table`, `query`, `explain`.
- An `explore-postgres` skill that walks the agent through orient → schema →
  sample → narrow query, and covers the engine's query format.

To tune approvals for the read-only tools, see the server policy in
`~/.codex/config.toml`:

```toml
[plugins."connectpak-postgres".mcp_servers.postgres]
default_tools_approval_mode = "approve"
```

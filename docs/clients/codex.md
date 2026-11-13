# Using connectpak with Codex

connectpak is one Codex plugin that covers all 24 engines.

## Install

```bash
codex plugin marketplace add arunvenkatadri/connectpak
codex plugin add connectpak@connectpak
```

Or browse the marketplace with `/plugins` inside Codex.

### From the OpenAI Plugins Directory

The directory listing carries the skills only, because the directory doesn't
accept MCP servers that run on your machine. After installing it, connect
the server once:

```bash
codex mcp add connectpak --env CONNECTPAK_CONNECTION="postgresql://reader:pw@localhost:5432/app" \
  -- uvx --from connectpak==0.1.0 connectpak
```

Add `--env CONNECTPAK_ENGINE=<engine>` when the engine isn't in the
connection string. This stores the connection in `~/.codex/config.toml`.

## Configure

Codex plugins don't prompt for settings, so the server reads the connection
from your environment. Export it before you start Codex:

```bash
export CONNECTPAK_CONNECTION="postgresql://reader:pw@localhost:5432/app"
export CONNECTPAK_ENGINE=bigquery   # only if the engine isn't in the connection
codex
```

If `CONNECTPAK_CONNECTION` isn't set, the server uses the engine's own
variable (such as `CONNECTPAK_POSTGRES_DSN`), as long as only one is set.

Codex doesn't pass your whole environment to MCP servers. The plugin
forwards only the variables it declares in `codex.mcp.json`: the two above,
every engine's own variable, and the AWS and Google credential variables
that DynamoDB and BigQuery use.

| Database | `CONNECTPAK_ENGINE` | `CONNECTPAK_CONNECTION` example |
| --- | --- | --- |
| Postgres | detected | `postgresql://reader:pw@db.example.com:5432/app` |
| SQLite | detected | `/Users/me/data/analytics.sqlite` |
| MySQL | detected | `mysql://reader:pw@db.example.com:3306/app` |
| ClickHouse | detected | `clickhouse://reader:pw@localhost:8123/default` |
| SQL Server | detected | `mssql://reader:pw@db.example.com:1433/app` |
| Oracle | `oracle` | `reader/pw@db.example.com:1521/ORCLPDB1` |
| BigQuery | `bigquery` | `my-gcp-project` |
| Snowflake | detected | `snowflake://user:pw@account/db/schema?warehouse=WH&role=READONLY` |
| Redshift | detected | `redshift://user:pw@host:5439/db` |
| Databricks | detected | `databricks://token:dapi-xxxxx@host.cloud.databricks.com?http_path=/sql/1.0/...` |
| MongoDB | detected | `mongodb://user:pw@host:27017/dbname` |
| DynamoDB | `dynamodb` | `us-east-1` |
| Elasticsearch | `elasticsearch` | `http://elastic:pw@localhost:9200` |
| Cassandra | `cassandra` | `user:pw@127.0.0.1:9042` |
| Neo4j | detected | `neo4j+s://neo4j:pw@cluster.example.com` |
| Memgraph | `memgraph` | `bolt://user:pw@localhost:7687` |
| ArangoDB | `arangodb` | `http://root:pw@localhost:8529/_system` |
| Amazon Neptune | detected | `wss://my-cluster.cluster-xxxx.us-east-1.neptune.amazonaws.com:8182/gremlin` |
| pgvector | `pgvector` | `postgresql://reader:pw@db.example.com:5432/app` |
| Pinecone | `pinecone` | `pcsk_xxxxx` |
| Weaviate | `weaviate` | `https://my-cluster.weaviate.network` |
| Qdrant | `qdrant` | `https://api-key@my-cluster.qdrant.io` |
| Chroma | `chroma` | `http://localhost:8000` |
| Milvus | `milvus` | `http://localhost:19530` |

The server starts with `uvx`, so [uv](https://docs.astral.sh/uv/) must be
on your `PATH`. The first start downloads the package and its drivers.

## What you get

- An MCP server named `connectpak` with six tools: `list_schemas`,
  `list_tables`, `describe_table`, `sample_table`, `query`, `explain`.
- Four skills, `explore-sql`, `explore-documents`, `explore-graph`, and
  `explore-vector`, that walk the agent through a safe workflow and each
  engine's query format.

To auto-approve the read-only tools, set the server's approval mode in
`~/.codex/config.toml`:

```toml
[plugins."connectpak".mcp_servers.connectpak]
default_tools_approval_mode = "approve"
```

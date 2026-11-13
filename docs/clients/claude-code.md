# Using connectpak with Claude Code

connectpak is one Claude Code plugin that covers all 24 engines.

## Install

```text
/plugin marketplace add arunvenkatadri/connectpak
/plugin install connectpak@connectpak
```

Or from a terminal, setting the connection directly:

```bash
claude plugin install connectpak --marketplace arunvenkatadri/connectpak \
  --config connection="postgresql://reader:pw@localhost:5432/app"
```

When the plugin is enabled, Claude Code asks for two settings:

- **Connection string** (required): the DSN, URL, path, or key for your
  database. It's marked sensitive, so it's kept in your OS credential store,
  not in `settings.json`.
- **Engine** (optional): only needed when the engine isn't in the connection
  string. See the table below.

To change them later, run `/plugin`, open `connectpak`, and edit its
configuration. To use two databases at once, add a second server with
`claude mcp add` (see the [Quick start](../../README.md#quick-start)).

The server starts with `uvx --from connectpak==<version> connectpak`, so
[uv](https://docs.astral.sh/uv/) must be on your `PATH`. The first start
downloads the package and its drivers (about 20 seconds). Later starts use
the cache.

| Database | Engine setting | Connection example |
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

## What you get

- An MCP server named `connectpak` with six tools: `list_schemas`,
  `list_tables`, `describe_table`, `sample_table`, `query`, `explain`.
  In Claude Code they appear as `mcp__plugin_connectpak_connectpak__<tool>`.
- Four skills, `explore-sql`, `explore-documents`, `explore-graph`, and
  `explore-vector`. They walk the agent through orient, schema, sample, and
  a narrow query, and cover each engine's query format.

To auto-approve the read-only tools, add this to your settings:

```json
{ "permissions": { "allow": ["mcp__plugin_connectpak_connectpak__*"] } }
```

## Cloud engines

- **BigQuery:** the connection is the GCP project ID, with engine
  `bigquery`. Auth uses Application Default Credentials
  (`gcloud auth application-default login`).
- **DynamoDB:** the connection is the AWS region, with engine `dynamodb`.
  Auth uses the standard AWS credential chain (`AWS_PROFILE`, env keys, SSO).

Use a read-only database role regardless. The connectors enforce read-only
twice, but defense in depth matters.

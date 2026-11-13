"""Registry of every connectpak engine.

This is the single source of truth for the `connectpak` launcher (which
engine handles a connection string) and for `scripts/gen_plugins.py`
(what the plugin documents and forwards). It must stay stdlib-only so the
generator can load it without installing anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field

AWS_ENV = (
    "AWS_PROFILE",
    "AWS_REGION",
    "AWS_DEFAULT_REGION",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_CONFIG_FILE",
    "AWS_SHARED_CREDENTIALS_FILE",
)
GCP_ENV = ("GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT", "CLOUDSDK_CONFIG")


@dataclass(frozen=True)
class Engine:
    key: str  # what users type for CONNECTPAK_ENGINE, e.g. "postgres"
    package: str  # directory under packages/, e.g. "sql-postgres"
    display: str
    family: str  # "sql" | "document" | "graph" | "vector"
    env_var: str  # the engine CLI's connection env var
    example: str
    # URL schemes that identify this engine unambiguously.
    schemes: tuple[str, ...] = ()
    # Cloud credential env vars the engine's SDK reads (forwarded by Codex).
    passthrough_env: tuple[str, ...] = field(default=())

    @property
    def cli(self) -> str:
        return f"connectpak-{self.package}"

    @property
    def module(self) -> str:
        track, name = self.package.split("-", 1)
        return f"connectpak.{track}.{name}.__main__"


ENGINES: tuple[Engine, ...] = (
    # SQL
    Engine("postgres", "sql-postgres", "Postgres", "sql", "CONNECTPAK_POSTGRES_DSN",
           "postgresql://reader:pw@db.example.com:5432/app", ("postgresql", "postgres")),
    Engine("sqlite", "sql-sqlite", "SQLite", "sql", "CONNECTPAK_SQLITE_PATH",
           "/Users/me/data/analytics.sqlite", ("sqlite",)),
    Engine("mysql", "sql-mysql", "MySQL", "sql", "CONNECTPAK_MYSQL_DSN",
           "mysql://reader:pw@db.example.com:3306/app", ("mysql", "mariadb")),
    Engine("clickhouse", "sql-clickhouse", "ClickHouse", "sql", "CONNECTPAK_CLICKHOUSE_DSN",
           "clickhouse://reader:pw@localhost:8123/default", ("clickhouse",)),
    Engine("sqlserver", "sql-sqlserver", "SQL Server", "sql", "CONNECTPAK_SQLSERVER_DSN",
           "mssql://reader:pw@db.example.com:1433/app", ("mssql", "sqlserver")),
    Engine("oracle", "sql-oracle", "Oracle", "sql", "CONNECTPAK_ORACLE_DSN",
           "reader/pw@db.example.com:1521/ORCLPDB1"),
    Engine("bigquery", "sql-bigquery", "BigQuery", "sql", "CONNECTPAK_BIGQUERY_PROJECT",
           "my-gcp-project", passthrough_env=GCP_ENV),
    Engine("snowflake", "sql-snowflake", "Snowflake", "sql", "CONNECTPAK_SNOWFLAKE_DSN",
           "snowflake://user:pw@account/db/schema?warehouse=WH&role=READONLY", ("snowflake",)),
    Engine("redshift", "sql-redshift", "Redshift", "sql", "CONNECTPAK_REDSHIFT_DSN",
           "redshift://user:pw@host:5439/db", ("redshift",)),
    Engine("databricks", "sql-databricks", "Databricks", "sql", "CONNECTPAK_DATABRICKS_DSN",
           "databricks://token:dapi-xxxxx@host.cloud.databricks.com?http_path=/sql/1.0/...",
           ("databricks",)),
    # Document / key-value / search
    Engine("mongodb", "nosql-mongodb", "MongoDB", "document", "CONNECTPAK_MONGODB_URI",
           "mongodb://user:pw@host:27017/dbname", ("mongodb", "mongodb+srv")),
    Engine("dynamodb", "nosql-dynamodb", "DynamoDB", "document", "CONNECTPAK_DYNAMODB_REGION",
           "us-east-1", passthrough_env=AWS_ENV),
    Engine("elasticsearch", "nosql-elasticsearch", "Elasticsearch", "document",
           "CONNECTPAK_ELASTICSEARCH_URL", "http://elastic:pw@localhost:9200"),
    Engine("cassandra", "nosql-cassandra", "Cassandra", "document",
           "CONNECTPAK_CASSANDRA_HOSTS", "user:pw@127.0.0.1:9042"),
    # Graph
    Engine("neo4j", "graph-neo4j", "Neo4j", "graph", "CONNECTPAK_NEO4J_URI",
           "neo4j+s://neo4j:pw@cluster.example.com",
           ("neo4j", "neo4j+s", "neo4j+ssc", "bolt", "bolt+s", "bolt+ssc")),
    Engine("memgraph", "graph-memgraph", "Memgraph", "graph", "CONNECTPAK_MEMGRAPH_URI",
           "bolt://user:pw@localhost:7687"),
    Engine("arangodb", "graph-arangodb", "ArangoDB", "graph", "CONNECTPAK_ARANGODB_URL",
           "http://root:pw@localhost:8529/_system"),
    Engine("neptune", "graph-neptune", "Amazon Neptune", "graph", "CONNECTPAK_NEPTUNE_URL",
           "wss://my-cluster.cluster-xxxx.us-east-1.neptune.amazonaws.com:8182/gremlin"),
    # Vector
    Engine("pgvector", "vector-pgvector", "pgvector", "vector", "CONNECTPAK_PGVECTOR_DSN",
           "postgresql://reader:pw@db.example.com:5432/app"),
    Engine("pinecone", "vector-pinecone", "Pinecone", "vector", "CONNECTPAK_PINECONE_API_KEY",
           "pcsk_xxxxx"),
    Engine("weaviate", "vector-weaviate", "Weaviate", "vector", "CONNECTPAK_WEAVIATE_URL",
           "https://my-cluster.weaviate.network"),
    Engine("qdrant", "vector-qdrant", "Qdrant", "vector", "CONNECTPAK_QDRANT_URL",
           "https://api-key@my-cluster.qdrant.io"),
    Engine("chroma", "vector-chroma", "Chroma", "vector", "CONNECTPAK_CHROMA_URL",
           "http://localhost:8000"),
    Engine("milvus", "vector-milvus", "Milvus", "vector", "CONNECTPAK_MILVUS_URI",
           "http://localhost:19530"),
)

BY_KEY: dict[str, Engine] = {e.key: e for e in ENGINES}

FAMILIES: dict[str, str] = {
    "sql": "SQL databases and warehouses",
    "document": "document, key-value, and search stores",
    "graph": "graph databases",
    "vector": "vector databases",
}

SQLITE_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".db3")

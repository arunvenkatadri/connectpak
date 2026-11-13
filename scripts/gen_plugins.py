"""Generate the Claude Code and Codex plugins under plugins/, plus both marketplaces.

Every engine package gets one plugin directory that serves both hosts:

    plugins/connectpak-<engine>/
    ├── .claude-plugin/plugin.json   # Claude Code: userConfig + inline mcpServers
    ├── .codex-plugin/plugin.json    # Codex: interface + pointer to codex.mcp.json
    ├── codex.mcp.json               # Codex: stdio server, forwards env vars
    └── skills/explore-<engine>/SKILL.md

The MCP server definitions differ per host on purpose. Claude Code prompts
for the connection string (userConfig) and injects it as the env var.
Codex has no equivalent prompt, so its server forwards the user's own
CONNECTPAK_* env var. That is also why the Codex config is not named
`.mcp.json`: Claude Code auto-loads a root `.mcp.json`, which would
register a second, unconfigured server.

Run from repo root:

    python scripts/gen_plugins.py           # write files
    python scripts/gen_plugins.py --check   # exit 1 if anything is stale (CI)

To try the plugins against unpushed connector changes, commit them and
generate with a local source (don't commit the result):

    python scripts/gen_plugins.py --source "file://$PWD" --ref my-branch
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES = ROOT / "packages"
PLUGINS = ROOT / "plugins"
QUERY_FORMATS = ROOT / "docs" / "query-formats.md"

REPO = "arunvenkatadri/connectpak"
REPO_URL = f"https://github.com/{REPO}"
# Git ref the plugins launch connectors from. None = repo default branch.
# Set to a release tag to pin plugin installs to a known-good version.
GIT_REF: str | None = None

AWS_ENV = [
    "AWS_PROFILE",
    "AWS_REGION",
    "AWS_DEFAULT_REGION",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_CONFIG_FILE",
    "AWS_SHARED_CREDENTIALS_FILE",
]
GCP_ENV = ["GOOGLE_APPLICATION_CREDENTIALS", "GOOGLE_CLOUD_PROJECT", "CLOUDSDK_CONFIG"]


@dataclass(frozen=True)
class Engine:
    package: str  # directory under packages/, e.g. "sql-postgres"
    display: str
    env_var: str  # the one env var the CLI reads its connection from
    connection_label: str
    example: str
    sensitive: bool = True
    # Extra env vars Codex must forward (it does not pass the full env).
    passthrough_env: list[str] = field(default_factory=list)
    keywords: tuple[str, ...] = ()

    @property
    def track(self) -> str:
        return self.package.split("-", 1)[0]

    @property
    def engine(self) -> str:
        return self.package.split("-", 1)[1]

    @property
    def plugin_name(self) -> str:
        return f"connectpak-{self.engine}"

    @property
    def cli(self) -> str:
        return f"connectpak-{self.package}"


ENGINES: list[Engine] = [
    # SQL
    Engine("sql-postgres", "Postgres", "CONNECTPAK_POSTGRES_DSN", "Postgres DSN",
           "postgresql://reader:pw@db.example.com:5432/app"),
    Engine("sql-sqlite", "SQLite", "CONNECTPAK_SQLITE_PATH", "SQLite database path",
           "/Users/me/data/analytics.sqlite", sensitive=False),
    Engine("sql-mysql", "MySQL", "CONNECTPAK_MYSQL_DSN", "MySQL DSN",
           "mysql://reader:pw@db.example.com:3306/app"),
    Engine("sql-clickhouse", "ClickHouse", "CONNECTPAK_CLICKHOUSE_DSN", "ClickHouse DSN",
           "clickhouse://reader:pw@localhost:8123/default"),
    Engine("sql-sqlserver", "SQL Server", "CONNECTPAK_SQLSERVER_DSN", "SQL Server DSN",
           "mssql://reader:pw@db.example.com:1433/app", keywords=("mssql", "tsql")),
    Engine("sql-oracle", "Oracle", "CONNECTPAK_ORACLE_DSN", "Oracle connect string",
           "reader/pw@db.example.com:1521/ORCLPDB1"),
    Engine("sql-bigquery", "BigQuery", "CONNECTPAK_BIGQUERY_PROJECT", "GCP project ID",
           "my-gcp-project", sensitive=False, passthrough_env=GCP_ENV, keywords=("gcp",)),
    Engine("sql-snowflake", "Snowflake", "CONNECTPAK_SNOWFLAKE_DSN", "Snowflake DSN",
           "snowflake://user:pw@account/db/schema?warehouse=WH&role=READONLY"),
    Engine("sql-redshift", "Redshift", "CONNECTPAK_REDSHIFT_DSN", "Redshift DSN",
           "redshift://user:pw@host:5439/db", keywords=("aws",)),
    Engine("sql-databricks", "Databricks", "CONNECTPAK_DATABRICKS_DSN", "Databricks DSN",
           "databricks://token:dapi-xxxxx@host.cloud.databricks.com?http_path=/sql/1.0/..."),
    # NoSQL
    Engine("nosql-mongodb", "MongoDB", "CONNECTPAK_MONGODB_URI", "MongoDB URI",
           "mongodb://user:pw@host:27017/dbname"),
    Engine("nosql-dynamodb", "DynamoDB", "CONNECTPAK_DYNAMODB_REGION", "AWS region",
           "us-east-1", sensitive=False, passthrough_env=AWS_ENV, keywords=("aws",)),
    Engine("nosql-elasticsearch", "Elasticsearch", "CONNECTPAK_ELASTICSEARCH_URL",
           "Elasticsearch URL", "http://elastic:pw@localhost:9200", keywords=("search",)),
    Engine("nosql-cassandra", "Cassandra", "CONNECTPAK_CASSANDRA_HOSTS",
           "Cassandra contact points", "user:pw@127.0.0.1:9042", keywords=("cql",)),
    # Graph
    Engine("graph-neo4j", "Neo4j", "CONNECTPAK_NEO4J_URI", "Neo4j Bolt URI",
           "bolt://neo4j:pw@localhost:7687", keywords=("cypher",)),
    Engine("graph-memgraph", "Memgraph", "CONNECTPAK_MEMGRAPH_URI", "Memgraph Bolt URI",
           "bolt://user:pw@localhost:7687", keywords=("cypher",)),
    Engine("graph-arangodb", "ArangoDB", "CONNECTPAK_ARANGODB_URL", "ArangoDB URL",
           "http://root:pw@localhost:8529/_system", keywords=("aql",)),
    Engine("graph-neptune", "Amazon Neptune", "CONNECTPAK_NEPTUNE_URL", "Neptune Gremlin URL",
           "wss://my-cluster.cluster-xxxx.us-east-1.neptune.amazonaws.com:8182/gremlin",
           keywords=("aws", "gremlin")),
    # Vector
    Engine("vector-pgvector", "pgvector", "CONNECTPAK_PGVECTOR_DSN", "Postgres DSN",
           "postgresql://reader:pw@db.example.com:5432/app", keywords=("postgres",)),
    Engine("vector-pinecone", "Pinecone", "CONNECTPAK_PINECONE_API_KEY", "Pinecone API key",
           "pcsk_xxxxx"),
    Engine("vector-weaviate", "Weaviate", "CONNECTPAK_WEAVIATE_URL", "Weaviate URL",
           "https://my-cluster.weaviate.network"),
    Engine("vector-qdrant", "Qdrant", "CONNECTPAK_QDRANT_URL", "Qdrant URL",
           "https://api-key@my-cluster.qdrant.io"),
    Engine("vector-chroma", "Chroma", "CONNECTPAK_CHROMA_URL", "Chroma server URL",
           "http://localhost:8000"),
    Engine("vector-milvus", "Milvus", "CONNECTPAK_MILVUS_URI", "Milvus URI",
           "http://localhost:19530"),
]

SQL_DIALECT = {
    "postgres": "Postgres",
    "sqlite": "SQLite",
    "mysql": "MySQL",
    "clickhouse": "ClickHouse",
    "sqlserver": "T-SQL",
    "oracle": "Oracle",
    "bigquery": "BigQuery Standard SQL",
    "snowflake": "Snowflake",
    "redshift": "Redshift",
    "databricks": "Databricks SQL",
    "pgvector": "Postgres, including pgvector operators such as `<=>`",
}
GRAPH_LANGUAGE = {
    "neo4j": "Cypher",
    "memgraph": "Cypher",
    "arangodb": "AQL",
    "neptune": "a Gremlin traversal string",
}
TRACK_LABEL = {"sql": "SQL", "nosql": "NoSQL", "graph": "graph", "vector": "vector"}


def _version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    return data["project"]["version"]


_source = REPO_URL
_ref = GIT_REF


def _launch_args(e: Engine) -> list[str]:
    ref = f"@{_ref}" if _ref else ""
    return [
        "--from",
        f"git+{_source}{ref}#subdirectory=packages/{e.package}",
        e.cli,
    ]


def _description(e: Engine) -> str:
    return (
        f"Read-only {e.display} access for AI agents over MCP: list schemas, "
        f"describe tables, sample rows, and run guarded queries."
    )


def _keywords(e: Engine) -> list[str]:
    return ["mcp", "database", "read-only", TRACK_LABEL[e.track].lower(), e.engine,
            *e.keywords]


def _common_manifest(e: Engine, version: str) -> dict:
    return {
        "name": e.plugin_name,
        "version": version,
        "description": _description(e),
        "author": {"name": "connectpak contributors", "url": REPO_URL},
        "homepage": REPO_URL,
        "repository": REPO_URL,
        "license": "MIT",
        "keywords": _keywords(e),
    }


def claude_manifest(e: Engine, version: str) -> dict:
    m = _common_manifest(e, version)
    m["userConfig"] = {
        "connection": {
            "type": "string",
            "title": e.connection_label,
            "description": f"Passed to the server as ${e.env_var}. Example: {e.example}. "
                           "Use read-only credentials.",
            "sensitive": e.sensitive,
            "required": True,
        }
    }
    m["mcpServers"] = {
        e.engine: {
            "command": "uvx",
            "args": _launch_args(e),
            "env": {e.env_var: "${user_config.connection}"},
        }
    }
    return m


def codex_manifest(e: Engine, version: str) -> dict:
    m = _common_manifest(e, version)
    m["skills"] = "./skills/"
    m["mcpServers"] = "./codex.mcp.json"
    m["interface"] = {
        "displayName": f"connectpak · {e.display}",
        "shortDescription": f"Read-only {e.display} access over MCP",
        "longDescription": (
            f"{_description(e)} Set ${e.env_var} in your environment before starting "
            f"Codex. Writes are rejected by a parser guard and by the engine's own "
            f"read-only mode; every query has a timeout and a row cap."
        ),
        "developerName": "connectpak",
        "category": "Developer Tools",
        "capabilities": ["Read"],
        "websiteURL": REPO_URL,
        "defaultPrompt": [f"What tables are in my {e.display} database?"],
    }
    return m


def codex_mcp(e: Engine) -> dict:
    return {
        "mcpServers": {
            e.engine: {
                "command": "uvx",
                "args": _launch_args(e),
                "env_vars": [e.env_var, *e.passthrough_env],
            }
        }
    }


def _query_format_section(e: Engine) -> str:
    if e.engine in SQL_DIALECT:
        return (
            f"`query` takes a SQL string in the {SQL_DIALECT[e.engine]} dialect. It is "
            "parsed with sqlglot and the whole tree is checked, so any statement that "
            "writes (including `SELECT ... INTO`, `FOR UPDATE`, or a write inside a CTE) "
            "is rejected."
        )
    if e.engine in GRAPH_LANGUAGE:
        return (
            f"`query` takes {GRAPH_LANGUAGE[e.engine]}. Writes are blocked by a keyword "
            "screen, which can also reject a read whose string literal contains a write "
            "keyword. If that happens, rephrase the query (e.g. use a parameter or a "
            "different literal)."
        )
    heading = {"elasticsearch": "Elasticsearch", "mongodb": "MongoDB",
               "dynamodb": "DynamoDB", "cassandra": "Cassandra"}.get(e.engine, e.display)
    text = QUERY_FORMATS.read_text()
    match = re.search(rf"^### {re.escape(heading)}\n(.*?)(?=^#{{2,3}} |\Z)", text,
                      re.MULTILINE | re.DOTALL)
    if not match:
        raise SystemExit(f"docs/query-formats.md has no '### {heading}' section")
    body = match.group(1).strip()
    if body.startswith("`query` takes"):  # the doc section already states the format
        return body
    return f"`query` takes a JSON spec (a JSON object, passed as a string):\n\n{body}"


def skill(e: Engine) -> str:
    return f"""---
name: explore-{e.engine}
description: Use when the user asks about data, tables, or schema in their {e.display} database, or wants a question answered from it. Explores and queries {e.display} read-only through the connectpak {e.engine} MCP tools.
---

# Explore {e.display} with connectpak

The `{e.engine}` MCP server from this plugin exposes six read-only tools:
`list_schemas`, `list_tables`, `describe_table`, `sample_table`, `query`,
and `explain`.

## Workflow

1. **Orient.** Call `list_schemas`, then `list_tables` (pass `schema` to
   narrow it). Don't guess table names.
2. **Read the schema before querying.** Call `describe_table` on every table
   you plan to touch. Use its foreign keys to work out joins instead of
   inferring them from column names.
3. **Look at real values.** Call `sample_table` when you need to know value
   formats, enums, or units before filtering on them.
4. **Query narrowly.** Select only the columns you need and filter early.
   For anything that might scan a large table, call `explain` first.
5. **Report honestly.** If a result has `truncated: true`, the row cap
   (default 1000) cut it off. Say so, then aggregate or filter instead of
   presenting partial rows as complete.

## Query format

{_query_format_section(e)}

## Read-only by design

Every write is rejected twice: by the parser guard and by the engine's own
read-only mode. Each query also has a statement timeout (default 30s). If
the user asks for a change (insert, update, delete, DDL), explain that this
connection is read-only and offer the statement for them to run themselves.
Never try to work around the guard.

## If the tools are missing or fail to start

The server needs `${e.env_var}` (example: `{e.example}`).

- **Claude Code:** run `/plugin`, open `{e.plugin_name}`, and set the
  connection, then restart the session.
- **Codex:** export `{e.env_var}` in the shell, then restart Codex.

The server is launched with `uvx`, so `uv` must be installed and on `PATH`.
"""


def claude_marketplace(version: str) -> dict:
    return {
        "name": "connectpak",
        "owner": {"name": "connectpak contributors", "url": REPO_URL},
        "metadata": {
            "description": "Read-only MCP database connectors for AI agents.",
            "version": version,
        },
        "plugins": [
            {
                "name": e.plugin_name,
                "source": f"./plugins/{e.plugin_name}",
                "description": _description(e),
                "version": version,
                "category": "database",
                "keywords": _keywords(e),
            }
            for e in ENGINES
        ],
    }


def codex_marketplace() -> dict:
    return {
        "name": "connectpak",
        "interface": {"displayName": "connectpak database connectors"},
        "plugins": [
            {
                "name": e.plugin_name,
                "source": {"source": "local", "path": f"./plugins/{e.plugin_name}"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": "Developer Tools",
            }
            for e in ENGINES
        ],
    }


def _json(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def render() -> dict[Path, str]:
    """Return every generated file as {path: content}."""
    version = _version()
    files: dict[Path, str] = {
        ROOT / ".claude-plugin" / "marketplace.json": _json(claude_marketplace(version)),
        ROOT / ".agents" / "plugins" / "marketplace.json": _json(codex_marketplace()),
    }
    for e in ENGINES:
        d = PLUGINS / e.plugin_name
        files[d / ".claude-plugin" / "plugin.json"] = _json(claude_manifest(e, version))
        files[d / ".codex-plugin" / "plugin.json"] = _json(codex_manifest(e, version))
        files[d / "codex.mcp.json"] = _json(codex_mcp(e))
        files[d / "skills" / f"explore-{e.engine}" / "SKILL.md"] = skill(e)
    return files


def check_engines() -> list[str]:
    """Cross-check the ENGINES table against the packages it describes."""
    errors = []
    packages = {p.name for p in PACKAGES.iterdir() if (p / "pyproject.toml").exists()}
    listed = {e.package for e in ENGINES}
    for missing in sorted(packages - listed - {"core"}):
        errors.append(f"packages/{missing} has no entry in ENGINES")
    for e in ENGINES:
        if e.package not in packages:
            errors.append(f"ENGINES lists {e.package}, which is not in packages/")
            continue
        pyproject = tomllib.loads((PACKAGES / e.package / "pyproject.toml").read_text())
        if e.cli not in pyproject.get("project", {}).get("scripts", {}):
            errors.append(f"packages/{e.package} does not define the {e.cli} script")
        main = next((PACKAGES / e.package / "src").rglob("__main__.py"), None)
        if main is None or e.env_var not in main.read_text():
            errors.append(f"packages/{e.package} CLI does not read ${e.env_var}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="Report stale or missing files instead of writing them.")
    parser.add_argument("--source", default=REPO_URL,
                        help="Git URL the plugins launch connectors from (testing only).")
    parser.add_argument("--ref", default=GIT_REF,
                        help="Git ref to launch connectors from (testing only).")
    args = parser.parse_args()
    global _source, _ref
    _source, _ref = args.source, args.ref

    errors = check_engines()
    if errors:
        print("\n".join(f"error: {m}" for m in errors), file=sys.stderr)
        return 1

    files = render()
    expected_dirs = {PLUGINS / e.plugin_name for e in ENGINES}
    stray = sorted(d for d in PLUGINS.glob("*") if d.is_dir() and d not in expected_dirs) \
        if PLUGINS.exists() else []

    if args.check:
        stale = [p for p, c in files.items() if not p.exists() or p.read_text() != c]
        for p in stale:
            print(f"stale: {p.relative_to(ROOT)}", file=sys.stderr)
        for d in stray:
            print(f"stray: {d.relative_to(ROOT)} (not in ENGINES)", file=sys.stderr)
        if stale or stray:
            print("run: python scripts/gen_plugins.py", file=sys.stderr)
            return 1
        print(f"plugins up to date ({len(ENGINES)} engines)")
        return 0

    for d in stray:
        shutil.rmtree(d)
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    print(f"wrote {len(files)} files for {len(ENGINES)} engines")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

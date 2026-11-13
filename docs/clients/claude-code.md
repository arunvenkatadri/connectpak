# Using connectpak with Claude Code

Each engine is a Claude Code plugin in the `connectpak` marketplace.

## Install

```text
/plugin marketplace add arunvenkatadri/connectpak
/plugin install connectpak-postgres@connectpak
```

Or from a terminal, setting the connection string directly:

```bash
claude plugin marketplace add arunvenkatadri/connectpak
claude plugin install connectpak-postgres@connectpak \
  --config connection="postgresql://reader:pw@localhost:5432/app"
```

When the plugin is enabled, Claude Code asks for its one setting, the
connection string, and hands it to the server as the engine's
`CONNECTPAK_*` env var. Connection strings that carry credentials are marked
sensitive and stored in your OS credential store, not in `settings.json`. To
change it later, run `/plugin`, open the plugin, and edit its configuration.

The server starts with `uvx`, so [uv](https://docs.astral.sh/uv/) must be on
your `PATH`. The first launch downloads the connector and its driver.

## What you get

- An MCP server named after the engine (for example `postgres`) with the six
  connectpak tools: `list_schemas`, `list_tables`, `describe_table`,
  `sample_table`, `query`, `explain`. In Claude Code they appear as
  `mcp__plugin_connectpak-postgres_postgres__<tool>`.
- An `explore-postgres` skill (`/connectpak-postgres:explore-postgres`)
  that walks the agent through orient → schema → sample → narrow query, and
  covers the engine's query format.

To auto-approve the read-only tools, add this to your settings:

```json
{ "permissions": { "allow": ["mcp__plugin_connectpak-postgres_postgres__*"] } }
```

## Cloud engines

- **BigQuery:** the setting is the GCP project ID. Auth uses Application
  Default Credentials (`gcloud auth application-default login`).
- **DynamoDB:** the setting is the AWS region. Auth uses the standard AWS
  credential chain (`AWS_PROFILE`, env keys, SSO).

Use a read-only database role regardless. The connectors enforce read-only
twice, but defense in depth matters.

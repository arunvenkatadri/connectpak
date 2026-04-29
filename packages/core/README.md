# connectpak-core

Core building blocks shared by every connectpak engine package:

- `BaseConnector` — abstract base class defining the connector contract.
- `assert_read_only` — sqlglot-based parser guard that blocks any
  state-mutating SQL before it ever reaches the engine.
- `build_server` / `serve` — turns a connector into a Model Context Protocol
  (MCP) server with six tools wrapping the connector methods.

You normally do not depend on this package directly — install one of the
engine packages (e.g. `connectpak-sql-postgres`) and it will pull `core` in
transitively.

# Privacy

connectpak is open-source software that runs entirely on your own machine.
It doesn't operate any service, and its maintainers receive no data from it.

## What connectpak does with your data

- **Connection details.** connectpak reads your connection string (a DSN,
  URL, file path, or API key) from its configuration or environment, and uses
  it only to connect to the database you named. It doesn't store it. In
  Claude Code the plugin's connection setting is kept by Claude Code in your
  operating system's credential store.
- **Database contents.** Schema information, sample rows, and query results
  go from your database to the AI agent you're using (for example Claude Code
  or Codex), because that's what you asked it to do. How that agent's provider
  handles them is covered by that provider's own terms and privacy policy.
- **No telemetry.** connectpak collects no analytics, usage data, or crash
  reports, and makes no network connections other than to your database (and,
  for cloud databases, the provider's authentication endpoints).
- **Package download.** When a plugin starts the server with `uvx`, uv
  downloads the `connectpak` package from PyPI. That download is between you
  and PyPI.

## Recommendations

Use a database role that can only read, and avoid connecting to databases
whose contents you don't want an AI agent to see.

## Contact

Questions or concerns: open an issue at
https://github.com/arunvenkatadri/connectpak/issues, or report a security
issue privately as described in [SECURITY.md](SECURITY.md).

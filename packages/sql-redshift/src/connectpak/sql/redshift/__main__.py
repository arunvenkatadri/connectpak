"""CLI entry point for the Redshift connector."""

from __future__ import annotations

import argparse
import os
import sys

from connectpak.core.server import serve
from connectpak.sql.redshift.connector import RedshiftConnector


def main() -> int:
    parser = argparse.ArgumentParser(prog="connectpak-sql-redshift")
    parser.add_argument(
        "--config",
        default=os.environ.get("CONNECTPAK_REDSHIFT_DSN"),
        help="Redshift connection config (default: $CONNECTPAK_REDSHIFT_DSN). "
             "See the connector's docstring for accepted formats.",
    )
    parser.add_argument("--allow-write", action="store_true")
    parser.add_argument("--statement-timeout-ms", type=int, default=30_000)
    parser.add_argument("--max-rows", type=int, default=1000)
    args = parser.parse_args()
    if not args.config:
        print(
            "error: --config is required (or set $CONNECTPAK_REDSHIFT_DSN)",
            file=sys.stderr,
        )
        return 2
    serve(RedshiftConnector(
        config=args.config,
        allow_write=args.allow_write,
        statement_timeout_ms=args.statement_timeout_ms,
        default_max_rows=args.max_rows,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""CLI entry point: `connectpak` — one command for every engine."""

from __future__ import annotations

import argparse
import os
import sys

from connectpak.launcher import (
    CONNECTION_VAR,
    ENGINE_VAR,
    PLUGIN_CONNECTION_VAR,
    PLUGIN_ENGINE_VAR,
    LaunchError,
    resolve,
    run,
    setting,
)
from connectpak.launcher.engines import ENGINES


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="connectpak",
        description="Serve any connectpak engine over MCP, read-only. The engine is "
                    "read from the connection string, or set with --engine.",
        epilog="Other options (--max-rows, --statement-timeout-ms, ...) are passed "
               "through to the engine's own CLI.",
    )
    env = dict(os.environ)
    parser.add_argument(
        "--connection", default=setting(env, CONNECTION_VAR, PLUGIN_CONNECTION_VAR),
        help=f"Connection string (default: ${CONNECTION_VAR} or ${PLUGIN_CONNECTION_VAR}).")
    parser.add_argument(
        "--engine", default=setting(env, ENGINE_VAR, PLUGIN_ENGINE_VAR),
        help=f"Engine if it can't be detected (default: ${ENGINE_VAR} or ${PLUGIN_ENGINE_VAR}).")
    parser.add_argument("--list-engines", action="store_true",
                        help="Print the supported engines and exit.")
    args, passthrough = parser.parse_known_args()

    if args.list_engines:
        for e in ENGINES:
            print(f"{e.key:<14} {e.display:<16} e.g. {e.example}")
        return 0

    try:
        engine, connection = resolve(args.connection, args.engine, env)
    except LaunchError as exc:
        print(f"connectpak: error: {exc}", file=sys.stderr)
        return 2
    print(f"connectpak: serving {engine.display} (read-only)", file=sys.stderr)
    return run(engine, connection, passthrough)


if __name__ == "__main__":
    raise SystemExit(main())

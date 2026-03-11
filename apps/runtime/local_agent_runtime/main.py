from __future__ import annotations

import argparse
import sys

from apps.runtime.local_agent_runtime.bootstrap import create_runtime_server
from packages.config.local_agent_config.loader import load_runtime_config
from packages.identity.local_agent_identity.loader import load_identity_bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local Agent Harness runtime shell")
    parser.add_argument(
        "--config",
        default="docs/architecture/runtime.example.toml",
        help="Path to the runtime config file.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_runtime_config(args.config)
    identity = load_identity_bundle(config.identity_path)
    server = create_runtime_server(config=config, identity=identity, config_path=args.config)
    return server.serve(sys.stdin, sys.stdout)


if __name__ == "__main__":
    raise SystemExit(main())

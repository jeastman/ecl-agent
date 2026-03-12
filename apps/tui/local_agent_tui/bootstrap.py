from __future__ import annotations

import argparse

from .app import AgentTUI, ensure_textual_available


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local Agent Harness TUI")
    parser.add_argument("--config", required=True, help="Path to the runtime config file.")
    parser.add_argument("--task-id", help="Optional task to inspect.")
    parser.add_argument("--run-id", help="Optional run to inspect.")
    return parser


def main(argv: list[str] | None = None) -> int:
    ensure_textual_available()
    args = build_parser().parse_args(argv)
    app = AgentTUI(config_path=args.config, task_id=args.task_id, run_id=args.run_id)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""CADiPy command-line adapter with stable exit codes."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .api import execute


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        if isinstance(exc.code, int):
            return exc.code
        return 2

    if args.command == "check" or (args.command == "server" and args.server_command == "status"):
        result = execute("diagnostics.connect")
    elif args.command == "operation":
        try:
            params: dict[str, Any] = json.loads(args.params_json)
        except json.JSONDecodeError as exc:
            sys.stdout.write(
                json.dumps(
                    {"ok": False, "error": {"code": "invalid_argument", "message": str(exc)}}
                )
                + "\n"
            )
            return 2
        result = execute(args.operation, params=params)
    else:
        parser.print_help()
        return 2

    sys.stdout.write(json.dumps(result.to_dict(), ensure_ascii=False, default=str) + "\n")
    return 0 if result.ok else 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cadipy")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("check", help="check the SolidWorks execution environment")
    server = subparsers.add_parser("server", help="inspect the protocol server")
    server_subparsers = server.add_subparsers(dest="server_command")
    server_subparsers.add_parser("status", help="check backend status")
    operation = subparsers.add_parser("operation", help="execute a registry operation")
    operation.add_argument("operation")
    operation.add_argument("--params-json", default="{}")
    return parser


if __name__ == "__main__":
    sys.exit(main())

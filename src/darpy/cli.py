"""Offline inspection commands for the DARPy platform foundation."""

from __future__ import annotations

import argparse
import json
import platform
from collections.abc import Sequence

from . import __version__
from .registry import capabilities
from .schemas import SCHEMA_VERSION, schema


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="darpy", description="Inspect the DARPy platform foundation")
    parser.add_argument("--version", action="version", version=f"darpy {__version__}")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor", help="Report local runtime facts without network access")
    commands.add_parser("capabilities", help="Show implemented, scoped, and planned capabilities")
    schema_parser = commands.add_parser("schema", help="Export a JSON Schema to standard output")
    schema_parser.add_argument("name", choices=("Task", "RunBudget", "RunResult"))
    args = parser.parse_args(argv)
    if args.command == "doctor":
        result = {
            "darpy_version": __version__,
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.system(),
            "schema_version": SCHEMA_VERSION,
            "core_external_dependencies": [],
            "execution": "local_cooperative",
            "full_numpy_parity": False,
            "full_sympy_parity": False,
            "full_matplotlib_parity": False,
        }
    elif args.command == "capabilities":
        result = {"capabilities": [item.to_dict() for item in capabilities()]}
    else:
        result = schema(args.name)
    print(json.dumps(result, indent=2, allow_nan=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

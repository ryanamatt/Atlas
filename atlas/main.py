# atlas/main.py

"""Command-line entry point for ``Atlas``."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from atlas import __version__
from atlas.commands import register_all
from atlas.errors import AtlasError


def main(argv: Sequence[str] | None = None) -> int:
    """
    Runs the Atlas command-line interface.

    Args:
        argv: The command-line arguments to parse, excluding the program
            name. If None, arguments are read from ``sys.argv``.

    Returns:
        The process exit code. Zero indicates success.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="A CLI tool for helping you with your Markdown Worldbuilding"
    )

    parser.add_argument(
        "--version",
        action="version",
        version=__version__,
        help="Return the version information of Atlas.",
    )

    parser.add_argument(
        "-v", "--vault", type=Path, help="Path to the Markdown worldbuilding vault."
    )

    parser.add_argument("--quiet", action="store_true", help="Silence any messages from Atlas.")

    parser.add_argument(
        "-j",
        "--json",
        dest="json_output",
        action="store_true",
        help=(
            "Print the result as JSON on standard output. Errors are printed as "
            "JSON on standard error. This is not affected by --quiet."
        ),
    )

    subparsers = parser.add_subparsers(dest="command", required=True, help="Available Commands")
    register_all(subparsers)

    args: argparse.Namespace = parser.parse_args(argv)

    try:
        return args.handler(args)
    except AtlasError as error:
        if args.json_output:
            payload: dict[str, dict[str, str]] = {
                "error": {"type": type(error).__name__, "message": str(error)}
            }
            print(json.dumps(payload, ensure_ascii=False), file=sys.stderr)
        else:
            print(f"atlas: {error}", file=sys.stderr)
        return error.exit_code

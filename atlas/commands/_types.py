# atlas/commands/_types.py

"""Shared typing helpers for Atlas subcommands."""

import argparse
from typing import Protocol


class SubParsers(Protocol):
    """
    The part of an argparse subparsers action that commands rely on.

    This mirrors ``argparse._SubParsersAction`` without importing the private
    class. Anything with a compatible ``add_parser`` method satisfies it.
    """

    def add_parser(
        self,
        name: str,
        *,
        help: str | None = None,  # noqa: A002
    ) -> argparse.ArgumentParser:
        """Adds a named subparser and returns it."""
        ...

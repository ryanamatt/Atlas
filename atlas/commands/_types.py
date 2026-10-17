# atlas/commands/_types.py

"""Shared typing helpers for Atlas subcommands."""

import argparse
from typing import Any, Protocol

import yaml


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


def non_empty(value: str) -> str:
    """
    Strips a command-line value and rejects it if nothing is left.

    Args:
        value: The raw value from the command line.

    Returns:
        The stripped value.

    Raises:
        argparse.ArgumentTypeError: If the value is empty or only whitespace.
    """
    stripped: str = value.strip()
    if not stripped:
        raise argparse.ArgumentTypeError("must not be empty")
    return stripped


def key_value(value: str) -> tuple[str, Any]:
    """
    Parses a ``KEY=VALUE`` command-line argument.

    The text is split at the first ``=``. The key is stripped of surrounding
    whitespace. The value is parsed as YAML, so ``2000000`` becomes an int,
    ``true`` a bool, ``[a, b]`` a list, and ``draft`` stays a string. Quote
    the value inside the argument to force a string, as in ``name="'123'"``.
    An empty value becomes ``None``.

    Args:
        value: The raw ``KEY=VALUE`` argument.

    Returns:
        The key and the parsed value.

    Raises:
        argparse.ArgumentTypeError: If there is no ``=``, the key is empty
            or is ``id``, or the value is not valid YAML.
    """
    key, separator, raw_value = value.partition("=")
    key = key.strip()
    if not separator or not key:
        raise argparse.ArgumentTypeError(f"expected KEY=VALUE, got {value!r}")
    if key == "id":
        raise argparse.ArgumentTypeError("'id' is set from the note path and cannot be changed")

    try:
        parsed: Any = yaml.safe_load(raw_value)
    except yaml.YAMLError as error:
        problem: str = getattr(error, "problem", None) or "invalid YAML"
        raise argparse.ArgumentTypeError(
            f"value for {key!r} is not valid YAML ({problem}); quote it to use it as text"
        ) from error
    return key, parsed

# atlas/commands/search_cmd.py

"""The atlas ``search`` command."""

import argparse

from atlas.commands._types import SubParsers
from atlas.note import Note
from atlas.vault import Vault

def register(subparsers: SubParsers) -> None:
    """
    Registers the ``search`` command.

    Args:
        subparsers: The subparsers action to add the command to.
    """
    parser: argparse.ArgumentParser = subparsers.add_parser(
        "search", help="Search for an Atlas Object."
    )
    parser.add_argument(
        "query",
        type=str,
        help="What to search for"
    )
    parser.set_defaults(handler=run)

def run(args: argparse.Namespace) -> int:
    """
    Runs the ``search`` command.

    Args:
        args: The parsed command-line arguments.

    Returns:
        The process exit code. Zero indicates success.
    
    Raises:
        VaultNotFoundError: If the vault path does not exist.
        VaultNotInitializedError: If the vault has no ``.atlas`` directory.
    """
    vault: Vault = Vault.open(args.vault)

    return 0


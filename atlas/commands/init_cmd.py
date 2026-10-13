# atlas/commands/init_cmd.py

"""The ``atlas init`` command."""

import argparse

from atlas.commands._types import SubParsers
from atlas.vault import Vault


def register(subparsers: SubParsers) -> None:
    """
    Registers the ``init`` subcommand.

    Args:
        subparsers: The subparsers action to add the command to.
    """
    parser: argparse.ArgumentParser = subparsers.add_parser(
        "init", help="Initialize an Atlas Project."
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    """
    Runs the ``init`` command.

    Args:
        args: The parsed command-line arguments.

    Returns:
        The process exit code. Zero indicates success.

    Raises:
        VaultNotFoundError: If the vault path does not exist.
        VaultAlreadyInitializedError: If the vault already has an ``.atlas``
            directory.
        FileCreationError: If the ``.atlas`` directory or its config file
            cannot be created.
    """
    Vault(args.vault).initialize()
    return 0

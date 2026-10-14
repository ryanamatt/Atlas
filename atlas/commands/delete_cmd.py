# atlas/commands/delete_cmd.py

"""The ``atlas delete`` command."""

import argparse

from atlas.commands._types import SubParsers
from atlas.vault import Vault


def register(subparsers: SubParsers) -> None:
    """
    Registers the ``delete`` subcommand.

    Args:
        subparsers: The subparsers action to add the command to.
    """
    parser: argparse.ArgumentParser = subparsers.add_parser(
        "delete", help="Delete an Atlas Object."
    )
    parser.add_argument(
        "name",
        type=str,
        help=(
            "Path of the item relative to the vault root, e.g. "
            "'Nations/Republic of Valora'. The '.md' extension is optional."
        ),
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    """
    Runs the ``delete`` command.

    Args:
        args: The parsed command-line arguments.

    Returns:
        The process exit code. Zero indicates success.

    Raises:
        VaultNotFoundError: If the vault path does not exist.
        VaultNotInitializedError: If the vault has no ``.atlas`` directory.
        InvalidNoteNameError: If the note name is not valid.
        NoteNotFoundError: If the note does not exist.
        FileCreationError: If the trash directory cannot be created.
        FileDeletionError: If the note cannot be moved to the trash.
    """
    vault: Vault = Vault.open(args.vault)
    vault.delete(vault.resolve_note(args.name))
    return 0

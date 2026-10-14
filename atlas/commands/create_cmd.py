# atlas/commands/create_cmd.py

"""The ``atlas create`` command."""

import argparse
from typing import TYPE_CHECKING

from atlas.commands._types import SubParsers
from atlas.vault import Vault

if TYPE_CHECKING:
    from atlas.note import Note

def register(subparsers: SubParsers) -> None:
    """
    Registers the ``create`` subcommand.

    Args:
        subparsers: The subparsers action to add the command to.
    """
    parser: argparse.ArgumentParser = subparsers.add_parser(
        "create", help="Create a new Atlas Object."
    )
    parser.add_argument(
        "name",
        type=str,
        help=(
            "Path of the new item relative to the vault root, e.g. "
            "'Nations/Republic of Valora'. The '.md' extension is optional."
        ),
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    """
    Runs the ``create`` command.

    Args:
        args: The parsed command-line arguments.

    Returns:
        The process exit code. Zero indicates success.

    Raises:
        VaultNotFoundError: If the vault path does not exist.
        VaultNotInitializedError: If the vault has no ``.atlas`` directory.
        InvalidNoteNameError: If the note name is not valid.
        NoteExistsError: If the note already exists.
        FileCreationError: If the note or its parent folders cannot be created.
    """
    vault: Vault = Vault.open(args.vault)
    new_note: Note = vault.resolve_note(args.name)
    vault.create(new_note)

    if not args.quiet:
        print("Created Note:", new_note.path)
    return 0

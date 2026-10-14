# atlas/commands/move_cmd.py

"""The ``atlas move`` command."""

import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from atlas.note import Note

from atlas.commands._types import SubParsers
from atlas.vault import Vault


def register(subparsers: SubParsers) -> None:
    """
    Registers the ``move`` subcommand.

    Args:
        subparsers: The subparsers action to add the command to.
    """
    parser: argparse.ArgumentParser = subparsers.add_parser(
        "move", help="Move or rename an Atlas note."
    )
    parser.add_argument(
        "source",
        type=str,
        help="Path of the existing note to move.",
    )
    parser.add_argument(
        "destination",
        type=str,
        help="New path or destination for the note.",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    """
    Runs the ``move`` command.

    Args:
        args: The parsed command-line arguments.

    Returns:
        The process exit code. Zero indicates success.

    Raises:
        VaultNotFoundError: If the vault path does not exist.
        VaultNotInitializedError: If the vault has no ``.atlas`` directory.
        InvalidNoteNameError: If either note name is not valid.
        NoteNotFoundError: If the source note does not exist.
        NoteExistsError: If the destination note already exists.
        FileReadError: If the source note cannot be read.
        InvalidFrontmatterError: If the source note's frontmatter is not valid.
        FileCreationError: If the destination's parent folders cannot be created.
        FileDeletionError: If the note cannot be moved.
        FileWriteError: If the note's new id cannot be written after the move.
    """
    vault: Vault = Vault.open(args.vault)
    source_note: Note = vault.resolve_note(args.source)
    dest_note: Note = vault.resolve_note(args.destination)

    vault.move(source_note, dest_note)
    return 0

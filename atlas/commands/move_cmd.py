# atlas/commands/move_cmd.py

"""The ``atlas move`` command."""

import argparse
from typing import TYPE_CHECKING

from atlas.commands._types import SubParsers
from atlas.vault import MoveResult, Vault

if TYPE_CHECKING:
    from atlas.note import Note


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
    parser.add_argument(
        "--no-links",
        dest="update_links",
        action="store_false",
        help="Do not update wiki links that point at the moved note.",
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
        FileWriteError: If the note's new id or an updated link cannot be
            written after the move.
        DirectoryReadError: If a directory in the vault cannot be read while
            looking for links.
    """
    vault: Vault = Vault.open(args.vault)
    source_note: Note = vault.resolve_note(args.source)
    dest_note: Note = vault.resolve_note(args.destination)

    result: MoveResult = vault.move(source_note, dest_note, update_links=args.update_links)

    if result.links_updated:
        links: str = "link" if result.links_updated == 1 else "links"
        notes: str = "note" if result.notes_updated == 1 else "notes"
        print(f"Updated {result.links_updated} {links} in {result.notes_updated} {notes}")

    return 0

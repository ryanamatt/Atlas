# atlas/commands/move_cmd.py

"""The ``atlas move`` command."""

import argparse
from typing import TYPE_CHECKING

from atlas.commands._types import SubParsers
from atlas.errors import (
    DuplicateDestinationError,
    NotAFolderError,
    NoteExistsError,
    NoteNotFoundError,
)

if TYPE_CHECKING:
    from pathlib import Path

from atlas.note import Note
from atlas.vault import MoveResult, Vault


def register(subparsers: SubParsers) -> None:
    """
    Registers the ``move`` subcommand.

    Args:
        subparsers: The subparsers action to add the command to.
    """
    parser: argparse.ArgumentParser = subparsers.add_parser(
        "move", help="Move or rename Atlas notes."
    )
    parser.add_argument(
        "sources",
        nargs="+",
        metavar="SOURCE",
        type=str,
        help="Path of an existing note to move. Give several to move them all.",
    )
    parser.add_argument(
        "destination",
        type=str,
        help=(
            "New path for a single note, or an existing folder to move "
            "notes into. Required to be a folder when there are several sources."
        ),
    )
    parser.add_argument(
        "--no-links",
        dest="update_links",
        action="store_false",
        help="Do not update wiki links that point at the moved notes.",
    )
    parser.set_defaults(handler=run)


def _plan_moves(vault: Vault, sources: list[str], destination: str) -> list[tuple[Note, Note]]:
    """
    Works out where every source note will go, and checks all of it up front.

    Nothing is moved until every pair has passed, so a bad argument never
    leaves the vault half moved.

    Args:
        vault: The vault the notes belong to.
        sources: The source names as typed.
        destination: The destination as typed.

    Returns:
        Each source note paired with the note it will become.

    Raises:
        InvalidNoteNameError: If a name is not valid.
        NotAFolderError: If there are several sources and the destination is
            not an existing folder.
        NoteNotFoundError: If a source note does not exist.
        NoteExistsError: If a destination note already exists.
        DuplicateDestinationError: If two notes would land on the same path.
    """
    source_notes: list[Note] = [vault.resolve_note(name) for name in sources]
    folder: Path | None = vault.resolve_folder(destination)

    pairs: list[tuple[Note, Note]]
    if folder is not None:
        pairs = [(note, Note(folder / note.path.name)) for note in source_notes]
    elif len(source_notes) == 1:
        pairs = [(source_notes[0], vault.resolve_note(destination))]
    else:
        raise NotAFolderError(destination)

    seen: set[Path] = set()
    for source, target in pairs:
        if not vault.note_exists(source):
            raise NoteNotFoundError(source.path)
        if vault.note_exists(target):
            raise NoteExistsError(target.path)
        if target.path in seen:
            raise DuplicateDestinationError(target.path)
        seen.add(target.path)

    return pairs


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
        InvalidNoteNameError: If a note name is not valid.
        NotAFolderError: If there are several sources and the destination is
            not an existing folder.
        NoteNotFoundError: If a source note does not exist.
        NoteExistsError: If a destination note already exists.
        DuplicateDestinationError: If two notes would land on the same path.
        FileReadError: If a note cannot be read.
        InvalidFrontmatterError: If a moved note's frontmatter is not valid.
        FileCreationError: If a destination's parent folders cannot be created.
        FileDeletionError: If a note cannot be moved.
        FileWriteError: If a note's new id or an updated link cannot be
            written after the move.
        DirectoryReadError: If a directory in the vault cannot be read while
            looking for links.
    """
    vault: Vault = Vault.open(args.vault)
    pairs: list[tuple[Note, Note]] = _plan_moves(vault, args.sources, args.destination)

    links_updated: int = 0
    notes_updated: int = 0
    for source, target in pairs:
        result: MoveResult = vault.move(source, target, update_links=args.update_links)
        links_updated += result.links_updated
        notes_updated += result.notes_updated

    if links_updated:
        links: str = "link" if links_updated == 1 else "links"
        notes: str = "note" if notes_updated == 1 else "notes"
        if not args.quiet:
            print(f"Updated {links_updated} {links} in {notes_updated} {notes}")

    return 0

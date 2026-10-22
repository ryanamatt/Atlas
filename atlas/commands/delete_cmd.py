# atlas/commands/delete_cmd.py

"""The ``atlas delete`` command."""

import argparse
from pathlib import Path

from atlas.commands._output import emit
from atlas.commands._types import SubParsers
from atlas.errors import DuplicateDestinationError, NoteNotFoundError
from atlas.note import Note
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
        "names",
        nargs="+",
        type=str,
        help=(
            "Path(s) of the item(s) relative to the vault root, e.g. "
            "'Nations/Republic of Valora'. The '.md' extension is optional."
        ),
    )
    parser.set_defaults(handler=run)


def _plan_deletes(vault: Vault, names: list[str]) -> list[Note]:
    """
    Resolves every name and checks all of them up front.

    Nothing is deleted until every note has passed, so a bad argument never
    leaves some notes in the trash and others not.

    Args:
        vault: The vault the notes belong to.
        names: The note names as typed.

    Returns:
        The notes to delete, in the order given.

    Raises:
        InvalidNoteNameError: If a name is not valid.
        DuplicateDestinationError: If the same note is named more than once.
        NoteNotFoundError: If a note does not exist.
    """
    notes: list[Note] = [vault.resolve_note(name) for name in names]

    seen: set[Path] = set()
    for note in notes:
        if note.path in seen:
            raise DuplicateDestinationError(note.path)
        seen.add(note.path)
        if not vault.note_exists(note):
            raise NoteNotFoundError(note.path)

    return notes


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
        InvalidNoteNameError: If a note name is not valid.
        DuplicateDestinationError: If the same note is named more than once.
        NoteNotFoundError: If a note does not exist.
        FileCreationError: If the trash directory cannot be created.
        FileDeletionError: If a note cannot be moved to the trash.
    """
    vault: Vault = Vault.open(args.vault)
    notes: list[Note] = _plan_deletes(vault, args.names)

    deleted: list[str] = []
    for note in notes:
        vault.delete(note)
        deleted.append(note.path.as_posix())

    if args.json_output:
        emit({"deleted": deleted})

    return 0

# atlas/commands/restore_cmd.py

"""The ``atlas restore`` command."""

import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from atlas.commands._output import emit
from atlas.commands._types import SubParsers
from atlas.errors import DuplicateDestinationError
from atlas.note import Note
from atlas.vault import Vault


def register(subparsers: SubParsers) -> None:
    """
    Registers the ``restore`` subcommand.

    Args:
        subparsers: The subparsers action to add the command to.
    """
    parser: argparse.ArgumentParser = subparsers.add_parser(
        "restore", help="Restore deleted Atlas notes from the trash."
    )
    parser.add_argument(
        "names",
        nargs="+",
        type=str,
        help=(
            "Original path(s) of the deleted note(s) relative to the vault root, e.g. "
            "'Nations/Republic of Valora'. The '.md' extension is optional. If a note "
            "was deleted more than once, the most recent version is restored."
        ),
    )
    parser.set_defaults(handler=run)


def _plan_restores(vault: Vault, names: list[str]) -> list[Note]:
    """
    Resolves every name and checks all of them up front.

    Nothing is restored until every note has passed, so a bad argument never
    leaves some notes restored and others not.

    Args:
        vault: The vault the notes belong to.
        names: The note names as typed.

    Returns:
        The notes to restore, in the order given.

    Raises:
        InvalidNoteNameError: If a name is not valid.
        DuplicateDestinationError: If the same note is named more than once.
        NoteNotInTrashError: If a note is not in the trash.
        NoteExistsError: If a note already exists at its original path.
        DirectoryReadError: If a trash directory cannot be read.
    """
    notes: list[Note] = [vault.resolve_note(name) for name in names]

    seen: set[Path] = set()
    for note in notes:
        if note.path in seen:
            raise DuplicateDestinationError(note.path)
        seen.add(note.path)
        vault.find_restorable(note)

    return notes


def run(args: argparse.Namespace) -> int:
    """
    Runs the ``restore`` command.

    Args:
        args: The parsed command-line arguments.

    Returns:
        The process exit code. Zero indicates success.

    Raises:
        VaultNotFoundError: If the vault path does not exist.
        VaultNotInitializedError: If the vault has no ``.atlas`` directory.
        InvalidNoteNameError: If a note name is not valid.
        DuplicateDestinationError: If the same note is named more than once.
        NoteNotInTrashError: If a note is not in the trash.
        NoteExistsError: If a note already exists at its original path.
        DirectoryReadError: If a trash directory cannot be read.
        FileCreationError: If a note's parent folders cannot be created.
        FileWriteError: If a note cannot be moved out of the trash.
    """
    vault: Vault = Vault.open(args.vault)
    notes: list[Note] = _plan_restores(vault, args.names)

    restored: list[str] = []
    for note in notes:
        vault.restore(note)
        restored.append(note.path.as_posix())

        if not args.quiet and not args.json_output:
            print("Restored Note:", note.path)

    if args.json_output:
        emit({"restored": restored})

    return 0

# atlas/commands/search_cmd.py

"""The atlas ``search`` command."""

import argparse
from collections.abc import Iterator
from pathlib import Path

from atlas.commands._types import SubParsers
from atlas.errors import DirectoryReadError
from atlas.note import Note
from atlas.vault import Vault

def register(subparsers: SubParsers) -> None:
    """
    Registers the ``search`` command.

    Args:
        subparsers: The subparsers action to add the command to.
    """
    parser: argparse.ArgumentParser = subparsers.add_parser(
        "search", help="Search for notes by title."
    )
    parser.add_argument(
        "query",
        type=str,
        help="Text to look for in note titles. The match is case-insensitive.",
    )
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="Search hidden directories too, such as the trash.",
    )
    parser.set_defaults(handler=run)

def _iter_notes(vault: Vault, include_hidden: bool = False) -> Iterator[Note]:
    """
    Walks the vault and yields every Markdown note in it.
 
    Symbolic links to directories are not followed, which keeps the search
    inside the vault. Hidden directories, such as ``.atlas`` and ``.trash``,
    are skipped unless ``include_hidden`` is set. Hidden files are skipped
    the same way.
 
    Args:
        vault: The vault to walk.
        include_hidden: Whether to include hidden files and directories.
 
    Yields:
        Each note found, in no particular order.
 
    Raises:
        DirectoryReadError: If a directory cannot be read.
    """
    def on_error(error: OSError) -> None:
        raise DirectoryReadError(Path(error.filename or vault.root), error.strerror)

    for directory, dirnames, filenames in Path(vault.root).walk(on_error=on_error):
        if not include_hidden:
            dirnames[:] = [name for name in dirnames if not name.startswith(".")]

        for filename in filenames:
            if not include_hidden and filename.startswith("."):
                continue
            if Note.is_note_name(filename):
                yield Note(vault, Path(directory) / filename)

def _matches_title(note: Note, query: str) -> bool:
    """
    Checks whether a note's title contains the query.
 
    The comparison is case-insensitive, and only the title (the file name
    without its suffix) is searched, not the folders above it.
 
    Args:
        note: The note to check.
        query: The text to look for.
 
    Returns:
        True if the title contains the query.
    """
    return query.casefold() in note.title.casefold()


def run(args: argparse.Namespace) -> int:
    """
    Runs the ``search`` command.
 
    Prints the vault-relative path of every note whose title contains the
    query, one per line, sorted by path. Printing nothing is not an error.
 
    Args:
        args: The parsed command-line arguments.
 
    Returns:
        The process exit code. Zero indicates success.
 
    Raises:
        VaultNotFoundError: If the vault path does not exist.
        VaultNotInitializedError: If the vault has no ``.atlas`` directory.
        DirectoryReadError: If a directory in the vault cannot be read.
    """
    vault: Vault = Vault.open(args.vault)
    query: str = args.query.strip()

    results: list[str] = sorted(
        (
            note.relative_path.as_posix()
            for note in _iter_notes(vault, include_hidden=args.all)
            if _matches_title(note, query)
        ),
        key=lambda path: (path.casefold(), path),
    )

    for path in results:
        print(path)

    return 0


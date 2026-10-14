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
            note.path.as_posix()
            for note in vault.iter_notes(include_hidden=args.all)
            if _matches_title(note, query)
        ),
        key=lambda path: (path.casefold(), path),
    )

    for path in results:
        print(path)

    return 0

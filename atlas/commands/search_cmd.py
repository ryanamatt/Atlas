# atlas/commands/search_cmd.py

"""The atlas ``search`` command."""

import argparse
from dataclasses import dataclass

from atlas import frontmatter
from atlas.commands._output import emit
from atlas.commands._types import SubParsers
from atlas.errors import InvalidFrontmatterError
from atlas.note import Note
from atlas.vault import Vault


@dataclass(frozen=True)
class BodyMatch:
    """
    One line of a note body that contains the query.

    Attributes:
        path: The vault-relative path of the note, with forward slashes.
        line: The 1-based line number in the note file. Frontmatter lines are
            counted, so the number matches what a text editor shows.
        text: The matching line with surrounding whitespace removed.
    """

    path: str
    line: int
    text: str


def register(subparsers: SubParsers) -> None:
    """
    Registers the ``search`` command.

    Args:
        subparsers: The subparsers action to add the command to.
    """
    parser: argparse.ArgumentParser = subparsers.add_parser(
        "search", help="Search for notes by title or body."
    )
    parser.add_argument(
        "query",
        type=str,
        help="Text to look for. The match is case-insensitive.",
    )
    parser.add_argument(
        "-b",
        "--body",
        action="store_true",
        help=(
            "Search the text of each note instead of its title. Frontmatter is "
            "not searched. Prints one line per match as PATH:LINE: TEXT."
        ),
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


def _body_matches(vault: Vault, note: Note, query: str) -> list[BodyMatch]:
    """
    Finds every line in a note's body that contains the query.

    The comparison is case-insensitive. Frontmatter is skipped, but its lines
    still count toward the line numbers. If the frontmatter is not valid, the
    whole file is searched instead, so one broken note does not stop a search.

    Args:
        vault: The vault that holds the note.
        note: The note to search.
        query: The text to look for.

    Returns:
        One match per matching line, in the order they appear in the note.

    Raises:
        FileReadError: If the note cannot be read.
    """
    text: str = vault.read_note(note)

    try:
        _, body = frontmatter.split(text)
    except InvalidFrontmatterError:
        body = text

    # The body is the end of the text, so what comes before it is the
    # frontmatter. Counting its newlines gives the lines to skip.
    first_line: int = text.count("\n", 0, len(text) - len(body)) + 1
    needle: str = query.casefold()
    path: str = note.path.as_posix()

    return [
        BodyMatch(path=path, line=number, text=line.strip())
        for number, line in enumerate(body.split("\n"), start=first_line)
        if needle in line.casefold()
    ]


def _search_titles(vault: Vault, query: str, include_hidden: bool) -> list[str]:
    """
    Finds the notes whose title contains the query.

    Args:
        vault: The vault to search.
        query: The text to look for.
        include_hidden: Whether to search hidden directories too.

    Returns:
        The vault-relative paths of the matching notes, sorted by path.
    """
    return sorted(
        (
            note.path.as_posix()
            for note in vault.iter_notes(include_hidden=include_hidden)
            if _matches_title(note, query)
        ),
        key=lambda path: (path.casefold(), path),
    )


def _search_bodies(vault: Vault, query: str, include_hidden: bool) -> list[BodyMatch]:
    """
    Finds every line in the vault's notes that contains the query.

    Args:
        vault: The vault to search.
        query: The text to look for.
        include_hidden: Whether to search hidden directories too.

    Returns:
        The matches, sorted by path and then by line number.

    Raises:
        FileReadError: If a note cannot be read.
    """
    matches: list[BodyMatch] = [
        match
        for note in vault.iter_notes(include_hidden=include_hidden)
        for match in _body_matches(vault, note, query)
    ]
    matches.sort(key=lambda match: (match.path.casefold(), match.path, match.line))
    return matches


def run(args: argparse.Namespace) -> int:
    """
    Runs the ``search`` command.

    By default, prints the vault-relative path of every note whose title
    contains the query, one per line, sorted by path. With ``--body``, prints
    ``PATH:LINE: TEXT`` for every line of a note body that contains the query,
    sorted by path and then line number. Printing nothing is not an error.

    With ``--json``, title results stay a list of paths. Body results are a
    list of objects with ``path``, ``line`` and ``text``.

    Args:
        args: The parsed command-line arguments.

    Returns:
        The process exit code. Zero indicates success.

    Raises:
        VaultNotFoundError: If the vault path does not exist.
        VaultNotInitializedError: If the vault has no ``.atlas`` directory.
        DirectoryReadError: If a directory in the vault cannot be read.
        FileReadError: With ``--body``, if a note cannot be read.
    """
    vault: Vault = Vault.open(args.vault)
    query: str = args.query.strip()

    if args.body:
        matches: list[BodyMatch] = _search_bodies(vault, query, args.all)

        if args.json_output:
            emit(
                {
                    "query": query,
                    "results": [
                        {"path": match.path, "line": match.line, "text": match.text}
                        for match in matches
                    ],
                }
            )
            return 0

        for match in matches:
            print(f"{match.path}:{match.line}: {match.text}")
        return 0

    results: list[str] = _search_titles(vault, query, args.all)

    if args.json_output:
        emit({"query": query, "results": results})
        return 0

    for path in results:
        print(path)

    return 0

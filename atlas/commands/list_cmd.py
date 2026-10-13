# atlas/commands/list_cmd.py

"""The ``atlas list`` command."""

import argparse
from pathlib import Path

from atlas.commands._types import SubParsers
from atlas.errors import DirectoryReadError
from atlas.note import Note
from atlas.vault import Vault

BRANCH: str = "├── "
LAST_BRANCH: str = "└── "
PIPE: str = "│   "
BLANK: str = "    "


def register(subparsers: SubParsers) -> None:
    """
    Registers the ``list`` subcommand.

    Args:
        subparsers: The subparsers action to add the command to.
    """
    parser: argparse.ArgumentParser = subparsers.add_parser(
        "list", help="List all Markdown files in an Atlas Project."
    )
    parser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="List hidden files and files in hidden directories.",
    )

    parser.set_defaults(handler=run)


def is_listed(item: Path, ignore_hidden: bool) -> bool:
    """
    Decides whether a directory entry belongs in the tree.

    Directories are always listed, so the structure of the vault stays
    visible. Files are listed only when they are Markdown files.

    Args:
        item: The directory entry to check.
        ignore_hidden: Whether entries whose name starts with ``.`` are skipped.

    Returns:
        True if the entry should appear in the tree.
    """
    if ignore_hidden and item.name.startswith("."):
        return False
    if item.is_dir():
        return True
    return item.is_file() and Note.is_note_name(item.name)


def sort_key(item: Path) -> tuple[bool, str, str]:
    """
    Orders directories before files, then names case-insensitively.

    The exact name is the final tie-breaker so the order is deterministic.

    Args:
        item: The directory entry to sort.

    Returns:
        A key suitable for ``sorted``.
    """
    return (not item.is_dir(), item.name.lower(), item.name)


def build_tree(path: Path, prefix: str = "", ignore_hidden: bool = True) -> list[str]:
    """
    Builds the lines of a visual tree for a directory.

    The whole tree is built before anything is printed, so a failure part way
    through never leaves half a tree on the screen. Symbolic links to
    directories are listed but never followed, which prevents infinite loops
    and keeps the listing inside the vault.

    Args:
        path: The directory to list.
        prefix: The prefix string used for formatting tree branches.
        ignore_hidden: Whether to ignore hidden files and directories (starting with '.').

    Returns:
        The tree, one line per entry.

    Raises:
        DirectoryReadError: If a directory cannot be read.
    """
    try:
        items: list[Path] = sorted(
            (item for item in path.iterdir() if is_listed(item, ignore_hidden)),
            key=sort_key,
        )
    except OSError as error:
        raise DirectoryReadError(path, error.strerror) from error

    lines: list[str] = []
    last_index: int = len(items) - 1

    for index, item in enumerate(items):
        is_last: bool = index == last_index
        lines.append(f"{prefix}{LAST_BRANCH if is_last else BRANCH}{item.name}")

        if item.is_dir() and not item.is_symlink():
            extension: str = BLANK if is_last else PIPE
            lines.extend(build_tree(item, prefix + extension, ignore_hidden))

    return lines


def run(args: argparse.Namespace) -> int:
    """
    Runs the ``list`` command.

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

    for line in build_tree(vault.root, ignore_hidden=not args.all):
        print(line)

    return 0

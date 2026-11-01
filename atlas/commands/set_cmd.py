# atlas/commands/set_cmd.py

"""The ``atlas set`` command."""

import argparse
from typing import Any

from atlas import frontmatter
from atlas.commands._output import emit
from atlas.commands._types import SubParsers
from atlas.errors import (
    InvalidFrontmatterError,
    InvalidNoteNameError,
    InvalidPropertyError,
    NoteNotFoundError,
)
from atlas.note import Note
from atlas.vault import Vault


def register(subparsers: SubParsers) -> None:
    """
    Registers the ``set`` subcommand.

    Args:
        subparsers: The subparsers action to add the command to.
    """
    parser: argparse.ArgumentParser = subparsers.add_parser(
        "set", help="Set frontmatter properties on existing notes."
    )

    parser.add_argument(
        "targets",
        nargs="+",
        metavar="NOTE... KEY=VALUE...",
        help=(
            "One or more notes followed by one or more KEY=VALUE pairs, e.g. "
            "'Nations/Valora status=draft population=2000000'. Existing keys are "
            "overwritten and new keys are added. Values are parsed as YAML, so "
            "numbers, booleans and lists work: 'tags=[nation, active]'. Quote the "
            "value inside the argument to force text: \"code='123'\". Note names "
            "must come first and cannot contain '='. The '.md' extension is optional."
        ),
    )

    parser.set_defaults(handler=run)


def _split_targets(targets: list[str]) -> tuple[list[str], list[str]]:
    """
    Splits the positional arguments into note names and ``KEY=VALUE`` pairs.

    Everything before the first argument that contains ``=`` is a note name.
    That argument and everything after it is a property assignment.

    Args:
        targets: The positional arguments as typed.

    Returns:
        The note names and the raw assignments.

    Raises:
        InvalidNoteNameError: If no note name comes before the assignments.
        InvalidPropertyError: If there are no assignments at all.
    """
    first: int | None = next((i for i, item in enumerate(targets) if "=" in item), None)
    if first is None:
        raise InvalidPropertyError(targets[-1], "expected at least one KEY=VALUE after the notes")
    if first == 0:
        raise InvalidNoteNameError(targets[0], "expected a note name before the KEY=VALUE pairs")
    return targets[:first], targets[first:]


def _parse_properties(assignments: list[str]) -> dict[str, Any]:
    """
    Parses every ``KEY=VALUE`` assignment into one mapping.

    If a key is given more than once, the last value wins.

    Args:
        assignments: The raw ``KEY=VALUE`` arguments.

    Returns:
        The properties to set, in the order they were first given.

    Raises:
        InvalidPropertyError: If an assignment is not valid.
    """
    properties: dict[str, Any] = {}
    for assignment in assignments:
        key, value = frontmatter.parse_property(assignment)
        properties[key] = value
    return properties


def _updated_text(vault: Vault, note: Note, properties: dict[str, Any]) -> str | None:
    """
    Builds the text of a note with the properties set in its frontmatter.

    Existing keys are overwritten in place and new keys are added at the end.
    A note without frontmatter gets a new frontmatter block. Windows line
    endings are kept if the note used them.

    Args:
        vault: The vault the note belongs to.
        note: The note to update.
        properties: The properties to set.

    Returns:
        The new text, or None if every property already has the given value,
        so the file does not need to be written.

    Raises:
        FileReadError: If the note cannot be read.
        InvalidFrontmatterError: If the note's frontmatter is not valid.
    """
    text: str = vault.read_note(note)

    try:
        data, body = frontmatter.split(text)
    except InvalidFrontmatterError as error:
        raise InvalidFrontmatterError(error.reason, note.path) from error

    changed: bool = False
    for key, value in properties.items():
        # The type check keeps 1 and True apart, since Python treats them as equal.
        if key not in data or data[key] != value or type(data[key]) is not type(value):
            data[key] = value
            changed = True

    if not changed:
        return None

    new_text: str = frontmatter.join(data, body)
    if "\r\n" in text:
        new_text = new_text.replace("\r\n", "\n").replace("\n", "\r\n")
    return new_text


def _plan_updates(
    vault: Vault, names: list[str], properties: dict[str, Any]
) -> list[tuple[Note, str | None]]:
    """
    Resolves every note and builds its new text before anything is written.

    Nothing is changed until every note has passed, so a bad argument never
    leaves some notes updated and others not. A note named more than once, for
    example as ``Valora`` and ``valora.md``, is only handled once.

    Args:
        vault: The vault the notes belong to.
        names: The note names as typed.
        properties: The properties to set.

    Returns:
        Each note with its new text, or None if it needs no change, in the
        order given.

    Raises:
        InvalidNoteNameError: If a note name is not valid.
        NoteNotFoundError: If a note does not exist.
        FileReadError: If a note cannot be read.
        InvalidFrontmatterError: If a note's frontmatter is not valid.
    """
    plan: list[tuple[Note, str | None]] = []
    seen: set[Note] = set()

    for name in names:
        note: Note = vault.resolve_note(name)
        if note in seen:
            continue
        seen.add(note)

        if not vault.note_exists(note):
            raise NoteNotFoundError(note.path)

        plan.append((note, _updated_text(vault, note, properties)))

    return plan


def run(args: argparse.Namespace) -> int:
    """
    Runs the ``set`` command.

    Args:
        args: The parsed command-line arguments.

    Returns:
        The process exit code. Zero indicates success.

    Raises:
        VaultNotFoundError: If the vault path does not exist.
        VaultNotInitializedError: If the vault has no ``.atlas`` directory.
        InvalidNoteNameError: If a note name is not valid.
        InvalidPropertyError: If a ``KEY=VALUE`` property is not valid.
        NoteNotFoundError: If a note does not exist.
        FileReadError: If a note cannot be read.
        InvalidFrontmatterError: If a note's frontmatter is not valid.
        FileWriteError: If a note cannot be written.
    """
    vault: Vault = Vault.open(args.vault)

    names, assignments = _split_targets(args.targets)
    properties: dict[str, Any] = _parse_properties(assignments)
    plan: list[tuple[Note, str | None]] = _plan_updates(vault, names, properties)

    keys: list[str] = list(properties)
    updated: list[dict[str, Any]] = []

    for note, new_text in plan:
        if new_text is None:
            if not args.quiet and not args.json_output:
                print("Unchanged Note: ", note.path)
            continue

        vault.write_note(note, new_text)
        updated.append({"path": note.path.as_posix(), "set": keys})

        if not args.quiet and not args.json_output:
            print("Updated Note: ", note.path)

    if args.json_output:
        emit({"updated": updated})

    return 0

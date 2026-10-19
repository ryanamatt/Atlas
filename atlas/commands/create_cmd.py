# atlas/commands/create_cmd.py

"""The ``atlas create`` command."""

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from atlas import frontmatter
from atlas.commands._output import emit
from atlas.commands._types import SubParsers, non_empty
from atlas.errors import FileReadError, InvalidNoteIdError
from atlas.vault import Vault

if TYPE_CHECKING:
    from atlas.note import Note


def register(subparsers: SubParsers) -> None:
    """
    Registers the ``create`` subcommand.

    Args:
        subparsers: The subparsers action to add the command to.
    """
    parser: argparse.ArgumentParser = subparsers.add_parser(
        "create", help="Create a new Atlas Object."
    )

    parser.add_argument(
        "names",
        nargs="+",
        type=str,
        help=(
            "Path(s) of the new item(s) relative to the vault root, e.g. "
            "'Nations/Republic of Valora'. The '.md' extension is optional."
        ),
    )

    parser.add_argument(
        "--type",
        type=non_empty,
        metavar="TYPE",
        help=(
            "Set the type of the new note, e.g. 'Nation'. Written to its frontmatter. "
            "Shorthand for --set type=<lowercased TYPE>."
        ),
    )

    parser.add_argument(
        "--set",
        dest="properties",
        action="append",
        metavar="KEY=VALUE",
        help=(
            "Set a frontmatter property, e.g. --set status=draft. The value is parsed "
            "as YAML, so numbers, booleans and lists work: --set population=2000000 "
            "--set 'tags=[nation, active]'. Repeatable. Overrides --type and the template."
        ),
    )

    parser.add_argument(
        "--id",
        type=non_empty,
        metavar="ID",
        dest="note_id",
        help=(
            "Use this ID instead of the one derived from the note's path. "
            "Only valid when creating a single note."
        ),
    )

    parser.add_argument(
        "-b",
        "--body",
        metavar="TEXT",
        help=(
            "Seed the note body with this text instead of the default heading or the "
            "template body. Use '-' to read the body from standard input. When creating "
            "several notes, every note gets the same body."
        ),
    )

    parser.add_argument(
        "-t",
        "--template",
        type=non_empty,
        metavar="NAME",
        help="Name of a template in .atlas/templates to start the note from.",
    )

    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the note (or last note) in the users $EDITOR. Does not open if no $EDITOR.",
    )

    parser.set_defaults(handler=run)


def _read_stdin() -> str:
    """
    Reads all of standard input as text.

    Returns:
        The text that was piped in.

    Raises:
        FileReadError: If standard input cannot be read or is not valid text.
    """
    try:
        return sys.stdin.read()
    except (OSError, UnicodeDecodeError) as error:
        reason: str = getattr(error, "strerror", None) or str(error)
        raise FileReadError(Path("<stdin>"), reason) from error


def run(args: argparse.Namespace) -> int:
    """
    Runs the ``create`` command.

    Args:
        args: The parsed command-line arguments.

    Returns:
        The process exit code. Zero indicates success.

    Raises:
        VaultNotFoundError: If the vault path does not exist.
        VaultNotInitializedError: If the vault has no ``.atlas`` directory.
        InvalidPropertyError: If a ``--set`` property is not valid.
        InvalidNoteNameError: If the note name is not valid.
        InvalidTemplateNameError: If the template name is not valid.
        TemplateNotFoundError: If the template does not exist.
        FileReadError: If the template cannot be read.
        InvalidFrontmatterError: If the template's frontmatter is not valid.
        NoteExistsError: If the note already exists.
        FileCreationError: If the note or its parent folders cannot be created.
    """
    vault: Vault = Vault.open(args.vault)

    if args.note_id is not None and len(args.names) > 1:
        raise InvalidNoteIdError(args.note_id, "--id can only be used when creating one note")

    properties: dict[str, Any] = {}
    if args.type is not None:
        properties["type"] = args.type.lower()

    raw_properties: list[str] = args.properties or []
    for assignment in raw_properties:
        key, value = frontmatter.parse_property(assignment)
        properties[key] = value

    body: str | None = args.body
    if body == "-":
        body = _read_stdin()

    last_note: Note | None = None
    created: list[dict[str, str]] = []

    for name in args.names:
        new_note: Note = vault.resolve_note(name)
        vault.create(
            new_note,
            properties=properties,
            template=args.template,
            note_id=args.note_id,
            body=body,
        )
        last_note = new_note
        created.append(
            {
                "path": new_note.path.as_posix(),
                "id": args.note_id if args.note_id is not None else new_note.note_id,
            }
        )

        if not args.quiet and not args.json_output:
            print("Created Note:", new_note.path)

    if args.json_output:
        emit({"created": created})

    if args.open and last_note is not None:
        editor: str | None = os.environ.get("EDITOR", None)
        if editor:
            try:
                cmd: list[str] = [*shlex.split(editor), str(last_note.path)]
                subprocess.call(cmd)  # noqa: S603
            except FileNotFoundError:
                print(
                    f"Editor '{editor}' not found.",
                    file=sys.stderr if args.json_output else sys.stdout,
                )
                return 0

    return 0

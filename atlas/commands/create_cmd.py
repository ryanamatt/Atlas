# atlas/commands/create_cmd.py

"""The ``atlas create`` command."""

import argparse
from typing import TYPE_CHECKING, Any

from atlas import frontmatter
from atlas.commands._types import SubParsers, non_empty
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
        "-t",
        "--template",
        type=non_empty,
        metavar="NAME",
        help="Name of a template in .atlas/templates to start the note from.",
    )

    parser.set_defaults(handler=run)


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

    properties: dict[str, Any] = {}
    if args.type is not None:
        properties["type"] = args.type.lower()

    raw_properties: list[str] = args.properties or []
    for assignment in raw_properties:
        key, value = frontmatter.parse_property(assignment)
        properties[key] = value

    for name in args.names:
        new_note: Note = vault.resolve_note(name)
        vault.create(new_note, properties=properties, template=args.template)

        if not args.quiet:
            print("Created Note:", new_note.path)
    return 0

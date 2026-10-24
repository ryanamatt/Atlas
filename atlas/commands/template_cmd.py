# atlas/commands/template_cmd.py

"""The ``atlas template`` command."""

import argparse
from pathlib import Path

from atlas.commands._editor import open_in_editor
from atlas.commands._output import emit
from atlas.commands._types import SubParsers, non_empty
from atlas.errors import DirectoryReadError
from atlas.vault import Vault


def register(subparsers: SubParsers) -> None:
    """
    Registers the ``template`` subcommand.

    Args:
        subparsers: The subparsers action to add the command to.
    """
    parser: argparse.ArgumentParser = subparsers.add_parser(
        "template", help="Handle Atlas templates."
    )

    template_subparsers = parser.add_subparsers(
        dest="template_action",
        required=True,
        help="Action to perform on templates.",
    )

    list_parser = template_subparsers.add_parser("list", help="List all available templates.")
    list_parser.set_defaults(handler=run_list)

    create_parser = template_subparsers.add_parser("create", help="Create a new template.")
    create_parser.add_argument(
        "name",
        type=non_empty,
        help="Name of the new template, e.g. 'Nation'. The '.md' extension is optional.",
    )
    create_parser.add_argument(
        "--open",
        action="store_true",
        help="Open the new template in the users $EDITOR. Does not open if no $EDITOR.",
    )
    create_parser.set_defaults(handler=run_create)


def _read_templates(templates_dir: Path) -> list[Path]:
    """
    Reads the template files in the templates directory in display order.

    Args:
        templates_dir: The directory that holds the templates.

    Returns:
        The template files, sorted case-insensitively by name.

    Raises:
        DirectoryReadError: If the directory cannot be read.
    """
    try:
        return sorted(
            (item for item in templates_dir.iterdir() if item.is_file()),
            key=lambda item: (item.name.lower(), item.name),
        )
    except OSError as error:
        raise DirectoryReadError(templates_dir, error.strerror) from error


def run_list(args: argparse.Namespace) -> int:
    """
    Runs the ``template list`` command.

    Args:
        args: The parsed command-line arguments.

    Returns:
        The process exit code. Zero indicates success.

    Raises:
        VaultNotFoundError: If the vault path does not exist.
        VaultNotInitializedError: If the vault has no ``.atlas`` directory.
        DirectoryReadError: If the templates directory cannot be read.
    """
    vault: Vault = Vault.open(args.vault)

    templates: list[Path] = (
        _read_templates(vault.templates_dir) if vault.templates_dir.exists() else []
    )

    if args.json_output:
        emit({"templates": [{"name": item.name} for item in templates]})
        return 0

    if not vault.templates_dir.exists():
        print("The template directory does not exist.")
        return 0

    for item in templates:
        print(item.name)

    return 0


def run_create(args: argparse.Namespace) -> int:
    """
    Runs the ``template create`` command.

    Args:
        args: The parsed command-line arguments.

    Returns:
        The process exit code. Zero indicates success.

    Raises:
        VaultNotFoundError: If the vault path does not exist.
        VaultNotInitializedError: If the vault has no ``.atlas`` directory.
        InvalidTemplateNameError: If the template name is not valid.
        TemplateExistsError: If the template already exists.
        FileCreationError: If the template or the templates directory cannot
            be created.
    """
    vault: Vault = Vault.open(args.vault)

    path: Path = vault.create_template(args.name)
    relative: Path = path.relative_to(vault.root)

    if args.json_output:
        emit({"created": {"name": path.stem, "path": relative.as_posix()}})
    elif not args.quiet:
        print("Created Template:", relative)

    if args.open:
        open_in_editor(path, args.json_output)

    return 0

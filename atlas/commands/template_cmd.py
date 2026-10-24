# atlas/commands/template_cmd.py

"""The ``atlas template`` command."""

import argparse
from pathlib import Path

from atlas.commands._output import emit
from atlas.commands._types import SubParsers
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

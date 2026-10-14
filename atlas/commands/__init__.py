# atlas/commands/__init__.py

"""Atlas subcommands."""

from atlas.commands import create_cmd, delete_cmd, init_cmd, list_cmd, move_cmd, search_cmd
from atlas.commands._types import SubParsers


def register_all(subparsers: SubParsers) -> None:
    """
    Registers every Atlas subcommand.

    Args:
        subparsers: The subparsers action to add the commands to.
    """
    init_cmd.register(subparsers)
    create_cmd.register(subparsers)
    list_cmd.register(subparsers)
    delete_cmd.register(subparsers)
    move_cmd.register(subparsers)
    search_cmd.register(subparsers)

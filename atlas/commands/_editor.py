# atlas/commands/_editor.py

"""Helpers for opening files in the user's editor."""

import os
import shlex
import subprocess
import sys
from pathlib import Path


def open_in_editor(path: Path, json_output: bool) -> None:
    """
    Opens a file in the editor named by the ``EDITOR`` environment variable.

    Nothing happens if ``EDITOR`` is not set. If the editor program cannot be
    found, a message is printed instead of raising an error, on standard error
    when ``--json`` is active so that standard output stays valid JSON.

    Args:
        path: The file to open.
        json_output: Whether ``--json`` is active.
    """
    editor: str | None = os.environ.get("EDITOR")
    if not editor:
        return

    try:
        subprocess.call([*shlex.split(editor), str(path)])  # noqa: S603
    except FileNotFoundError:
        print(
            f"Editor '{editor}' not found.",
            file=sys.stderr if json_output else sys.stdout,
        )

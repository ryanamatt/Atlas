# atlas/commands/_output.py

"""Helpers for the machine-readable output of ``--json``."""

import json
from typing import Any


def emit(data: Any) -> None:
    """
    Prints one JSON document to standard output.

    Non-ASCII characters are written as they are, so note names in any
    language stay readable.

    Args:
        data: The JSON-serializable value to print.
    """
    print(json.dumps(data, ensure_ascii=False, indent=2))

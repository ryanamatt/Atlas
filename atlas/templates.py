# atlas/templates.py

"""Handles the templates in the Atlas Vault."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import Any


_PLACEHOLDER_RE: re.Pattern[str] = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def render(text: str, values: Mapping[str, Any]) -> str:
    """
    Renders a template string by replacing {{name}} placeholders with values.

    Unknown placeholders (keys not present in values) are left unchanged.

    Args:
        text: The template text containing placeholders.
        values: A mapping of placeholder names to their replacement values.

    Returns:
        The rendered text.
    """

    def replace(match: re.Match[str]) -> str:
        key: str = match.group(1)
        if key in values:
            return str(values[key])
        return match.group(0)

    return _PLACEHOLDER_RE.sub(replace, text)


def render_data(data: Mapping[str, Any], values: Mapping[str, Any]) -> dict[str, Any]:
    """
    Renders placeholders in every string inside parsed frontmatter.

    Strings are rendered, lists and mappings are walked recursively, and
    every other value is kept as it is.

    Args:
        data: The parsed frontmatter.
        values: A mapping of placeholder names to their replacement values.

    Returns:
        A copy of the frontmatter with its strings rendered.
    """
    return {key: _render_value(value, values) for key, value in data.items()}


def _render_value(value: object, values: Mapping[str, Any]) -> object:
    """
    Renders placeholders in one parsed YAML value.

    Args:
        value: A string, list, mapping, or any other parsed YAML value.
        values: A mapping of placeholder names to their replacement values.

    Returns:
        The value with every string inside it rendered.
    """
    if isinstance(value, str):
        return render(value, values)
    if isinstance(value, list):
        items: list[object] = cast("list[object]", value)
        return [_render_value(item, values) for item in items]
    if isinstance(value, dict):
        mapping: dict[object, object] = cast("dict[object, object]", value)
        return {str(key): _render_value(item, values) for key, item in mapping.items()}
    return value

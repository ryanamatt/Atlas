# atlas/frontmatter.py

"""Reading and writing the YAML frontmatter at the top of a note."""

import re
import sys
import unicodedata
from typing import Any, cast

import yaml

from atlas.errors import InvalidFrontmatterError, InvalidPropertyError

FENCE: str = "---"

_FRONTMATTER_RE: re.Pattern[str] = re.compile(
    r"\A---[ \t]*\r?\n(?P<yaml>.*?)^---[ \t]*(?:\r?\n|\Z)",
    re.DOTALL | re.MULTILINE,
)
_NON_SLUG_RE: re.Pattern[str] = re.compile(r"[\W_]+")


def slugify(text: str) -> str:
    """
    Turns text into a lowercase, hyphen-separated slug.

    Letters and digits from any language are kept. Every run of other
    characters, such as spaces and punctuation, becomes a single hyphen, and
    hyphens at either end are removed.

    Args:
        text: The text to convert, for example a note title.

    Returns:
        The slug, for example ``republic-of-valora``. This is an empty string
        if the text has no letters or digits.
    """
    normalized: str = unicodedata.normalize("NFKC", text).casefold()
    return _NON_SLUG_RE.sub("-", normalized).strip("-")


def split(text: str) -> tuple[dict[str, Any], str]:
    """
    Splits a note into its frontmatter and its body.

    Frontmatter is a YAML block between two ``---`` lines at the very start of
    the text. A note without one has empty frontmatter and keeps all of its
    text as the body.

    Args:
        text: The full text of a note.

    Returns:
        The parsed frontmatter and the body that follows it. A single blank
        line after the closing fence is not part of the body.

    Raises:
        InvalidFrontmatterError: If the block is not valid YAML or is not a
            mapping of keys to values.
    """
    match: re.Match[str] | None = _FRONTMATTER_RE.match(text)
    if match is None:
        return {}, text

    try:
        raw_data: Any = yaml.safe_load(match["yaml"])
    except yaml.YAMLError as error:
        raise InvalidFrontmatterError(str(error)) from error

    if raw_data is None:
        data: dict[Any, Any] = {}
    elif not isinstance(raw_data, dict):
        raise InvalidFrontmatterError("frontmatter must be a mapping of keys to values")
    else:
        data = cast("dict[Any, Any]", raw_data)

    body: str = text[match.end() :]
    body = body.removeprefix("\r\n") if body.startswith("\r\n") else body.removeprefix("\n")
    return {str(key): value for key, value in data.items()}, body


def join(data: dict[str, Any], body: str) -> str:
    """
    Builds note text from frontmatter and a body.

    Keys keep the order they have in ``data``. With no data, no frontmatter
    block is written at all.

    Args:
        data: The frontmatter to write.
        body: The text that follows the frontmatter.

    Returns:
        The full text of the note.
    """
    if not data:
        return body

    block: str = yaml.safe_dump(
        data,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=sys.maxsize,
    )
    return f"{FENCE}\n{block}{FENCE}\n\n{body}"


def parse_property(assignment: str) -> tuple[str, Any]:
    """
    Parses a ``KEY=VALUE`` property given on the command line.

    The text is split at the first ``=``. The key is stripped of surrounding
    whitespace. The value is parsed as YAML, so ``2000000`` becomes an int,
    ``true`` a bool, ``[a, b]`` a list, and ``draft`` stays a string. Quote the
    value inside the argument to force a string, as in ``name="'123'"``. An
    empty value becomes ``None``.

    Args:
        assignment: The raw ``KEY=VALUE`` text.

    Returns:
        The key and the parsed value.

    Raises:
        InvalidPropertyError: If there is no ``=``, the key is empty or is
            ``id``, or the value is not valid YAML.
    """
    key, separator, raw_value = assignment.partition("=")
    key = key.strip()
    if not separator or not key:
        raise InvalidPropertyError(assignment, "expected KEY=VALUE")
    if key == "id":
        raise InvalidPropertyError(assignment, "'id' is set from the note path")

    try:
        value: Any = yaml.safe_load(raw_value)
    except yaml.YAMLError as error:
        problem: str = getattr(error, "problem", None) or "invalid YAML"
        raise InvalidPropertyError(
            assignment, f"value is not valid YAML ({problem}), quote it to use it as text"
        ) from error
    return key, value

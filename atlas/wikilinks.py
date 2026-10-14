# atlas/wikilinks.py

"""Finding and rewriting ``[[wiki links]]`` in note text."""

import re
from collections.abc import Callable

_LINK_RE: re.Pattern[str] = re.compile(
    r"(?P<embed>!?)\[\["
    r"(?P<target>[^\[\]|#\\\n]+)"
    r"(?P<anchor>#[^\[\]|\\\n]*)?"
    r"(?P<alias>\\?\|[^\[\]\n]*)?"
    r"\]\]"
)

# Fenced code blocks (an unclosed fence runs to the end of the text) and
# inline code spans. Links inside either are examples, not real links.
_CODE_RE: re.Pattern[str] = re.compile(
    r"^[ \t]*(?P<fence>`{3,}(?![^\n]*`)|~{3,}).*?(?:^[ \t]*(?P=fence)[ \t]*$|\Z)"
    r"|(?P<tick>`+)(?!`)[^\n]+?(?<!`)(?P=tick)(?!`)",
    re.DOTALL | re.MULTILINE,
)


def rewrite(text: str, replace: Callable[[str], str | None]) -> tuple[str, int]:
    """
    Rewrites the target of every wiki link in a piece of text.

    Handles ``[[target]]``, ``[[target|alias]]``, ``[[target#Heading]]`` and
    embeds such as ``![[target]]``. Only the target is changed. The embed
    marker, heading, alias, and any escaped pipe used inside Markdown tables
    are kept exactly as written. Links inside code blocks and inline code are
    left alone.

    Args:
        text: The text to search.
        replace: Called with each link target, stripped of surrounding
            whitespace. It returns the new target, or None to leave the link
            as it is.

    Returns:
        The new text and the number of links that were changed.
    """
    changed: int = 0

    def substitute(match: re.Match[str]) -> str:
        nonlocal changed
        target: str = match["target"]
        stripped: str = target.strip()
        if not stripped:
            return match[0]

        new_target: str | None = replace(stripped)
        if new_target is None or new_target == stripped:
            return match[0]

        changed += 1
        lead: str = target[: len(target) - len(target.lstrip())]
        trail: str = target[len(target.rstrip()) :]
        return (
            f"{match['embed']}[[{lead}{new_target}{trail}"
            f"{match['anchor'] or ''}{match['alias'] or ''}]]"
        )

    parts: list[str] = []
    position: int = 0
    for code in _CODE_RE.finditer(text):
        parts.append(_LINK_RE.sub(substitute, text[position : code.start()]))
        parts.append(code[0])
        position = code.end()
    parts.append(_LINK_RE.sub(substitute, text[position:]))

    return "".join(parts), changed

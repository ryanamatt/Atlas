# atlas/note.py

"""The ``Note`` object, which represents a Markdown note in a vault."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

from atlas import frontmatter
from atlas.errors import InvalidFrontmatterError

MARKDOWN_SUFFIX: str = ".md"


@dataclass(frozen=True)
class Note:
    """
    A Markdown note, identified by its path inside a vault.

    A ``Note`` knows nothing about the file system or the vault that holds it.
    It is only a value, so it may describe a note that does not exist yet. Use
    ``Vault.resolve_note`` to build one from user input, and the vault's
    methods to create, read, move, or delete it.

    Attributes:
        path: The path of the note file, relative to the vault root.
    """

    path: Path

    @staticmethod
    def is_note_name(name: str) -> bool:
        """
        Checks whether a file name ends with the Markdown suffix.

        The comparison is case-insensitive.

        Args:
            name: The file name or path string to check.

        Returns:
            True if the name ends with ``.md`` in any letter case.
        """
        return name.lower().endswith(MARKDOWN_SUFFIX)

    @property
    def title(self) -> str:
        """The note title, which is its file name without the suffix."""
        return self.path.stem

    @property
    def note_id(self) -> str:
        """
        The note id, which is a slug of its path inside the vault.

        The ``.md`` suffix is left out and folders are included, so
        ``Nations/Republic of Valora.md`` has the id
        ``nations-republic-of-valora``. The id changes whenever the note moves.
        """
        return frontmatter.slugify(self.path.with_suffix("").as_posix())

    def text_with_id(self, text: str, new_id: str) -> str | None:
        """
        Builds note text with its frontmatter id set to a new value.

        Only a default id is rewritten. If the note's ``id`` is not the one
        derived from its current path, it was set by hand (for example with
        ``atlas create --id``), so it is kept as it is. Call this on the note
        as it is before the move, because the current path is what decides
        whether the id is a default one.

        Args:
            text: The current full text of the note.
            new_id: The id to write.

        Returns:
            The updated text, or None if the note has no ``id`` in its
            frontmatter, has a custom ``id``, or already has ``new_id``, so
            nothing needs rewriting.

        Raises:
            InvalidFrontmatterError: If the note's frontmatter is not valid.
        """
        try:
            data, body = frontmatter.split(text)
        except InvalidFrontmatterError as error:
            raise InvalidFrontmatterError(error.reason, self.path) from error

        current_id: object = data.get("id")
        if current_id != self.note_id or current_id == new_id:
            return None

        data["id"] = new_id
        return frontmatter.join(data, body)

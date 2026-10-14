# atlas/note.py

"""The ``Note`` object, which represents a Markdown note in a vault."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

from atlas import frontmatter
from atlas.errors import (
    DirectoryReadError,
    FileCreationError,
    FileDeletionError,
    FileReadError,
    FileWriteError,
    InvalidFrontmatterError,
    InvalidNoteNameError,
    NoteExistsError,
    NoteNotFoundError,
)
from atlas.vault import ATLAS_DIRNAME, Vault

MARKDOWN_SUFFIX: str = ".md"


class Note:
    """
    A Markdown note that lives inside a vault.

    Build a note from user input with ``Note.from_name``, which validates the
    name. The plain constructor trusts that ``path`` is already a valid note
    path inside the vault. Creating a ``Note`` never touches the file system,
    so it may describe a note that does not exist yet.

    Attributes:
        vault: The vault the note belongs to.
        path: The absolute path of the note file.
    """

    def __init__(self, vault: Vault, path: Path) -> None:
        """
        Creates a note object for a path inside a vault.

        Args:
            vault: The vault the note belongs to.
            path: The absolute path of the note file.
        """
        self.vault: Vault = vault
        self.path: Path = path

    @classmethod
    def from_name(cls, vault: Vault, name: str) -> Note:
        """
        Builds a note from a user-supplied name.

        A ``.md`` extension is appended unless the name already ends with one
        (case-insensitive). The result must stay inside the vault and must not
        point into the ``.atlas`` directory.

        Args:
            vault: The vault the note belongs to.
            name: The name given on the command line, relative to the vault
                root.

        Returns:
            The note for that name.

        Raises:
            InvalidNoteNameError: If the name is empty, ends with a path
                separator, has no file name, has no letters or digits to build
                an id from, escapes the vault, or points into the ``.atlas``
                directory.
        """
        cleaned: str = name.strip()

        if not cleaned or cleaned.endswith(("/", "\\")):
            raise InvalidNoteNameError(name, "name is empty or ends with a separator")

        if not cls.is_note_name(cleaned):
            cleaned += MARKDOWN_SUFFIX

        note_path: Path = (vault.root / cleaned).resolve()

        if not note_path.is_relative_to(vault.root):
            raise InvalidNoteNameError(name, "path is outside the vault")

        if note_path.name.lower() == MARKDOWN_SUFFIX:
            raise InvalidNoteNameError(name, "name has no file name")

        if note_path.is_relative_to(vault.atlas_dir):
            raise InvalidNoteNameError(name, f"path is inside the {ATLAS_DIRNAME} directory")

        if not frontmatter.slugify(note_path.stem):
            raise InvalidNoteNameError(name, "name has no letters or digits to build an id from")

        return cls(vault, note_path)

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

    @staticmethod
    def iter_notes(vault: Vault, include_hidden: bool = False) -> Iterator[Note]:
        """
        Walks the vault and yields every Markdown note in it.

        Symbolic links to directories are not followed, which keeps the search
        inside the vault. Hidden directories, such as ``.atlas`` and ``.trash``,
        are skipped unless ``include_hidden`` is set. Hidden files are skipped
        the same way.

        Args:
            vault: The vault to walk.
            include_hidden: Whether to include hidden files and directories.

        Yields:
            Each note found, in no particular order.

        Raises:
            DirectoryReadError: If a directory cannot be read.
        """

        def on_error(error: OSError) -> None:
            raise DirectoryReadError(Path(error.filename or vault.root), error.strerror)

        for directory, dirnames, filenames in Path(vault.root).walk(on_error=on_error):
            if not include_hidden:
                dirnames[:] = [name for name in dirnames if not name.startswith(".")]

            for filename in filenames:
                if not include_hidden and filename.startswith("."):
                    continue
                if Note.is_note_name(filename):
                    yield Note(vault, Path(directory) / filename)

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
        return frontmatter.slugify(self.relative_path.with_suffix("").as_posix())

    @property
    def relative_path(self) -> Path:
        """The path of the note relative to the vault root."""
        return self.path.relative_to(self.vault.root)

    def exists(self) -> bool:
        """
        Checks whether the note file exists.

        Returns:
            True if the file exists.
        """
        return self.path.is_file()

    def read_text(self) -> str:
        """
        Reads the whole note file.

        Line endings are returned exactly as they are on disk.

        Returns:
            The text of the note.

        Raises:
            FileReadError: If the file cannot be read or is not valid UTF-8.
        """
        try:
            with self.path.open(encoding="utf-8", newline="") as file:
                return file.read()
        except (OSError, UnicodeDecodeError) as error:
            reason = getattr(error, "strerror", None) or str(error)
            raise FileReadError(self.path, reason) from error

    def write_text(self, text: str) -> None:
        """
        Replaces the whole note file with new text.

        Line endings are written exactly as given.

        Args:
            text: The text to write.

        Raises:
            FileWriteError: If the file cannot be written.
        """
        try:
            with self.path.open("w", encoding="utf-8", newline="") as file:
                file.write(text)
        except OSError as error:
            raise FileWriteError(self.path, error.strerror) from error

    def create(self) -> None:
        """
        Creates the note file, along with any missing parent folders.

        The note starts with YAML frontmatter holding its id, followed by a
        top-level heading taken from its title.

        Raises:
            NoteExistsError: If the note already exists.
            FileCreationError: If the note or its parent folders cannot be
                created.
        """
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise FileCreationError(self.path.parent, error.strerror) from error

        try:
            with self.path.open("x", encoding="utf-8") as file:
                file.write(frontmatter.join({"id": self.note_id}, f"# {self.title}\n"))
        except FileExistsError as error:
            raise NoteExistsError(self.relative_path) from error
        except OSError as error:
            raise FileCreationError(self.path, error.strerror) from error

    def delete(self) -> None:
        """
        Moves the note into the vault's trash directory.

        The note keeps its relative path inside the trash, and a timestamp
        is added to its name so repeated deletions never collide.

        Raises:
            NoteNotFoundError: If the note does not exist.
            FileCreationError: If the trash directory cannot be created.
            FileDeletionError: If the note cannot be moved to the trash.
        """
        if not self.exists():
            raise NoteNotFoundError(self.relative_path)

        trash_dir: Path = self.vault.ensure_trash_exists()
        stamp: str = datetime.now().strftime("%Y%m%d-%H%M%S")
        destination: Path = (
            trash_dir / self.relative_path.parent / f"{self.path.stem}.{stamp}{self.path.suffix}"
        )

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(self.path, destination)
        except (OSError, shutil.Error) as error:
            reason = getattr(error, "strerror", None) or str(error)
            raise FileDeletionError(self.path, reason) from error

    def move(self, destination: Note) -> None:
        """
        Moves or renames the note to a new destination note path.

        Creates any missing parent directories for the destination. If the
        note has an ``id`` in its frontmatter, the id is rewritten to match the
        new path. A note without an ``id`` is moved unchanged. The note is read
        before anything moves, so an unreadable note or broken frontmatter
        stops the command with nothing changed.

        Args:
            destination: The note at the new path.

        Raises:
            NoteNotFoundError: If the source note does not exist.
            NoteExistsError: If a note already exists at the destination.
            FileReadError: If the note cannot be read.
            InvalidFrontmatterError: If the note's frontmatter is not valid.
            FileCreationError: If parent folders cannot be created.
            FileDeletionError: If the note cannot be moved.
            FileWriteError: If the new id cannot be written after the move.
        """
        if not self.exists():
            raise NoteNotFoundError(self.relative_path)

        if destination.exists():
            raise NoteExistsError(destination.relative_path)

        updated_text: str | None = self._text_with_id(destination.note_id)

        try:
            destination.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise FileCreationError(destination.path.parent, error.strerror) from error

        try:
            shutil.move(self.path, destination.path)
        except (OSError, shutil.Error) as error:
            reason = getattr(error, "strerror", None) or str(error)
            raise FileDeletionError(self.path, reason) from error

        if updated_text is not None:
            destination.write_text(updated_text)

    def _text_with_id(self, new_id: str) -> str | None:
        """
        Builds the note text with its frontmatter id set to a new value.

        Args:
            new_id: The id to write.

        Returns:
            The updated text, or None if the note has no ``id`` in its
            frontmatter or already has this one, so nothing needs rewriting.

        Raises:
            FileReadError: If the note cannot be read.
            InvalidFrontmatterError: If the note's frontmatter is not valid.
        """
        try:
            data, body = frontmatter.split(self.read_text())
        except InvalidFrontmatterError as error:
            raise InvalidFrontmatterError(error.reason, self.relative_path) from error

        if "id" not in data or data["id"] == new_id:
            return None

        data["id"] = new_id
        return frontmatter.join(data, body)

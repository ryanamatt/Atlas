# atlas/vault.py

"""The ``Vault`` object, which represents a Markdown worldbuilding vault."""

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
    InvalidNoteNameError,
    NoteExistsError,
    NoteNotFoundError,
    VaultAlreadyInitializedError,
    VaultNotFoundError,
    VaultNotInitializedError,
)
from atlas.note import MARKDOWN_SUFFIX, Note

ATLAS_DIRNAME: str = ".atlas"
CONFIG_FILENAME: str = "config.toml"
TRASH_DIRNAME: str = ".trash"

DEFAULT_CONFIG: str = """\
# Atlas vault configuration.
 
schema_version = 1
"""

MAX_PARENT_SEARCH: int = 5


class Vault:
    """
    A Markdown worldbuilding vault on disk.

    A ``Vault`` owns everything that depends on where the vault lives: its
    root path, its ``.atlas`` directory, the rules for turning note names into
    notes, and every operation that reads or changes note files. Notes are
    plain values that are only meaningful relative to a vault. Creating a
    ``Vault`` never touches the file system, so it is safe to build one for a
    path that does not exist yet.

    Attributes:
        root: The resolved absolute path of the vault root.
    """

    def __init__(self, root: Path | str | None = None) -> None:
        """
        Creates a vault object for a Path.

        Args:
            root: The vault path given on the command line, or None to use the current working
            directory.
        """
        self.root: Path = Path(root or ".").resolve()

    @classmethod
    def open(cls, root: Path | str | None = None) -> Vault:
        """
        Creates a vault object and makes sure the vault is initialized.

        An explicit path is used as given. Without one, Atlas searches the
        current directory and its parents for an ``.atlas`` directory.

        Args:
            root: The vault path given on the command line, or None to use
                the current working directory.

        Returns:
            A vault whose root exists and has an ``.atlas`` directory.

        Raises:
            VaultNotFoundError: If the vault path does not exist.
            VaultNotInitializedError: If the vault has no ``.atlas``
                directory.
        """
        vault: Vault = cls(root) if root is not None else cls.discover()
        vault.require_initialized()
        return vault

    @classmethod
    def discover(
        cls,
        start: Path | str | None = None,
        max_parents: int = MAX_PARENT_SEARCH,
    ) -> Vault:
        """
        Looks for an initialized vault in a directory and its parents.

        The search checks ``start`` first, then up to ``max_parents`` of its
        ancestors, and stops at the first one with an ``.atlas`` directory.

        Args:
            start: The directory to start from, or None for the current
                working directory.
            max_parents: How many parent directories to check after ``start``.

        Returns:
            The first initialized vault found. If none is found, a vault for
            ``start`` itself, so ``require_initialized`` reports the error
            for the directory the user is actually in.
        """
        origin: Path = Path(start or ".").resolve()
        candidates: tuple[Path, ...] = (origin, *origin.parents)

        for candidate in candidates[: max_parents + 1]:
            vault: Vault = cls(candidate)
            if vault.is_initialized():
                return vault

        return cls(origin)

    @property
    def atlas_dir(self) -> Path:
        """The path of the ``.atlas`` directory. It may not exist yet."""
        return self.root / ATLAS_DIRNAME

    @property
    def config_path(self) -> Path:
        """The path of the vault config file. It may not exist yet."""
        return self.atlas_dir / CONFIG_FILENAME

    @property
    def trash_dir(self) -> Path:
        """The path of the trash directory. It may not exist yet."""
        return self.root / TRASH_DIRNAME

    def is_initialized(self) -> bool:
        """
        Checks whether the vault has an ``.atlas`` directory.

        Returns:
            True if the ``.atlas`` directory exists.
        """
        return self.atlas_dir.is_dir()

    def require_initialized(self) -> None:
        """
        Checks that the vault exists and is initialized.

        Raises:
            VaultNotFoundError: If the vault path does not exist.
            VaultNotInitializedError: If the vault has no ``.atlas``
                directory.
        """
        if not self.root.exists():
            raise VaultNotFoundError(self.root)
        if not self.is_initialized():
            raise VaultNotInitializedError(self.root)

    def initialize(self) -> None:
        """
        Creates the ``.atlas`` directory and its default config file.

        Raises:
            VaultNotFoundError: If the vault path does not exist.
            VaultAlreadyInitializedError: If the vault already has an
                ``.atlas`` directory.
            FileCreationError: If the ``.atlas`` directory or its config file
                cannot be created.
        """
        if not self.root.exists():
            raise VaultNotFoundError(self.root)

        try:
            self.atlas_dir.mkdir()
        except FileExistsError as error:
            raise VaultAlreadyInitializedError(self.root) from error
        except OSError as error:
            raise FileCreationError(self.atlas_dir, error.strerror) from error

        try:
            self.config_path.write_text(DEFAULT_CONFIG, encoding="utf-8")
        except OSError as error:
            raise FileCreationError(self.config_path, error.strerror) from error

    def ensure_trash_exists(self) -> Path:
        """
        Creates the trash directory if it does not exist yet.

        Returns:
            The path of the trash directory.

        Raises:
            FileCreationError: If the trash directory cannot be created.
        """
        try:
            self.trash_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise FileCreationError(self.trash_dir, error.strerror) from error
        return self.trash_dir

    # ------------------------------------------------------------------
    # Notes
    # ------------------------------------------------------------------

    def resolve_note(self, name: str) -> Note:
        """
        Builds a note from a user-supplied name.

        A ``.md`` extension is appended unless the name already ends with one
        (case-insensitive). The result must stay inside the vault and must not
        point into the ``.atlas`` directory. Nothing is read from disk beyond
        resolving the path, so the note may not exist yet.

        Args:
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

        if not Note.is_note_name(cleaned):
            cleaned += MARKDOWN_SUFFIX

        note_path: Path = (self.root / cleaned).resolve()

        if not note_path.is_relative_to(self.root):
            raise InvalidNoteNameError(name, "path is outside the vault")

        if note_path.name.lower() == MARKDOWN_SUFFIX:
            raise InvalidNoteNameError(name, "name has no file name")

        if note_path.is_relative_to(self.atlas_dir):
            raise InvalidNoteNameError(name, f"path is inside the {ATLAS_DIRNAME} directory")

        if not frontmatter.slugify(note_path.stem):
            raise InvalidNoteNameError(name, "name has no letters or digits to build an id from")

        return Note(note_path.relative_to(self.root))

    def path_of(self, note: Note) -> Path:
        """
        Gives the absolute path of a note file in this vault.

        Args:
            note: The note to locate.

        Returns:
            The absolute path. The file may not exist.
        """
        return self.root / note.path

    def note_exists(self, note: Note) -> bool:
        """
        Checks whether a note file exists in this vault.

        Args:
            note: The note to check.

        Returns:
            True if the file exists.
        """
        return self.path_of(note).is_file()

    def iter_notes(self, include_hidden: bool = False) -> Iterator[Note]:
        """
        Walks the vault and yields every Markdown note in it.

        Symbolic links to directories are not followed, which keeps the search
        inside the vault. Hidden directories, such as ``.atlas`` and ``.trash``,
        are skipped unless ``include_hidden`` is set. Hidden files are skipped
        the same way.

        Args:
            include_hidden: Whether to include hidden files and directories.

        Yields:
            Each note found, in no particular order.

        Raises:
            DirectoryReadError: If a directory cannot be read.
        """

        def on_error(error: OSError) -> None:
            raise DirectoryReadError(Path(error.filename or self.root), error.strerror)

        for directory, dirnames, filenames in self.root.walk(on_error=on_error):
            if not include_hidden:
                dirnames[:] = [name for name in dirnames if not name.startswith(".")]

            for filename in filenames:
                if not include_hidden and filename.startswith("."):
                    continue
                if Note.is_note_name(filename):
                    yield Note((directory / filename).relative_to(self.root))

    def read_note(self, note: Note) -> str:
        """
        Reads the whole note file.

        Line endings are returned exactly as they are on disk.

        Args:
            note: The note to read.

        Returns:
            The text of the note.

        Raises:
            FileReadError: If the file cannot be read or is not valid UTF-8.
        """
        path: Path = self.path_of(note)
        try:
            with path.open(encoding="utf-8", newline="") as file:
                return file.read()
        except (OSError, UnicodeDecodeError) as error:
            reason = getattr(error, "strerror", None) or str(error)
            raise FileReadError(path, reason) from error

    def write_note(self, note: Note, text: str) -> None:
        """
        Replaces the whole note file with new text.

        Line endings are written exactly as given.

        Args:
            note: The note to write.
            text: The text to write.

        Raises:
            FileWriteError: If the file cannot be written.
        """
        path: Path = self.path_of(note)
        try:
            with path.open("w", encoding="utf-8", newline="") as file:
                file.write(text)
        except OSError as error:
            raise FileWriteError(path, error.strerror) from error

    def create(self, note: Note) -> None:
        """
        Creates the note file, along with any missing parent folders.

        The note starts with YAML frontmatter holding its id, followed by a
        top-level heading taken from its title.

        Args:
            note: The note to create.

        Raises:
            NoteExistsError: If the note already exists.
            FileCreationError: If the note or its parent folders cannot be
                created.
        """
        path: Path = self.path_of(note)

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise FileCreationError(path.parent, error.strerror) from error

        try:
            with path.open("x", encoding="utf-8") as file:
                file.write(frontmatter.join({"id": note.note_id}, f"# {note.title}\n"))
        except FileExistsError as error:
            raise NoteExistsError(note.path) from error
        except OSError as error:
            raise FileCreationError(path, error.strerror) from error

    def delete(self, note: Note) -> None:
        """
        Moves a note into the vault's trash directory.

        The note keeps its relative path inside the trash, and a timestamp
        is added to its name so repeated deletions never collide.

        Args:
            note: The note to delete.

        Raises:
            NoteNotFoundError: If the note does not exist.
            FileCreationError: If the trash directory cannot be created.
            FileDeletionError: If the note cannot be moved to the trash.
        """
        if not self.note_exists(note):
            raise NoteNotFoundError(note.path)

        trash_dir: Path = self.ensure_trash_exists()
        stamp: str = datetime.now().strftime("%Y%m%d-%H%M%S")
        destination: Path = (
            trash_dir / note.path.parent / f"{note.path.stem}.{stamp}{note.path.suffix}"
        )

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(self.path_of(note), destination)
        except (OSError, shutil.Error) as error:
            reason = getattr(error, "strerror", None) or str(error)
            raise FileDeletionError(self.path_of(note), reason) from error

    def move(self, source: Note, destination: Note) -> None:
        """
        Moves or renames a note to a new destination.

        Creates any missing parent directories for the destination. If the
        note has an ``id`` in its frontmatter, the id is rewritten to match the
        new path. A note without an ``id`` is moved unchanged. The note is read
        before anything moves, so an unreadable note or broken frontmatter
        stops the command with nothing changed.

        Args:
            source: The note to move.
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
        if not self.note_exists(source):
            raise NoteNotFoundError(source.path)

        if self.note_exists(destination):
            raise NoteExistsError(destination.path)

        updated_text: str | None = source.text_with_id(self.read_note(source), destination.note_id)

        source_path: Path = self.path_of(source)
        destination_path: Path = self.path_of(destination)

        try:
            destination_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise FileCreationError(destination_path.parent, error.strerror) from error

        try:
            shutil.move(source_path, destination_path)
        except (OSError, shutil.Error) as error:
            reason = getattr(error, "strerror", None) or str(error)
            raise FileDeletionError(source_path, reason) from error

        if updated_text is not None:
            self.write_note(destination, updated_text)

# atlas/vault.py

"""The ``Vault`` object, which represents a Markdown worldbuilding vault."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping
    from typing import Any

from atlas import frontmatter, wikilinks
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


@dataclass(frozen=True)
class MoveResult:
    """
    What a move changed besides the note itself.

    Attributes:
        links_updated: How many wiki links were rewritten.
        notes_updated: How many notes had at least one link rewritten.
    """

    links_updated: int = 0
    notes_updated: int = 0


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

    def create(self, note: Note, properties: Mapping[str, Any] | None = None) -> None:
        """
        Creates the note file, along with any missing parent folders.

        The note starts with YAML frontmatter holding its id, then any extra
        properties in the order given, followed by a top-level heading taken
        from its title.

        Args:
            note: The note to create.
            properties: Extra frontmatter to write after the id, such as
                ``{"type": "Nation"}``. The id always comes from the note's path.

        Raises:
            NoteExistsError: If the note already exists.
            FileCreationError: If the note or its parent folders cannot be
                created.
        """
        path: Path = self.path_of(note)
        data: dict[str, Any] = {"id": note.note_id}
        data.update({key: value for key, value in (properties or {}).items() if key != "id"})

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise FileCreationError(path.parent, error.strerror) from error

        try:
            with path.open("x", encoding="utf-8") as file:
                file.write(frontmatter.join(data, f"# {note.title}\n"))
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

    def move(self, source: Note, destination: Note, update_links: bool = True) -> MoveResult:
        """
        Moves or renames a note to a new destination.

        Creates any missing parent directories for the destination. If the
        note has an ``id`` in its frontmatter, the id is rewritten to match the
        new path. A note without an ``id`` is moved unchanged.

        Unless ``update_links`` is False, wiki links to the note are rewritten
        in every visible note of the vault, including the moved note itself.
        A link written as a full path gets the new path. A link written as a
        bare title is only changed when the title changes, or when the bare
        title would no longer point at one note. A bare title that several
        notes share is left alone, because it is unclear which note it meant.

        Args:
            source: The note to move.
            destination: The note at the new path.
            update_links: Whether to rewrite wiki links that point at the note.

        Returns:
            How many links and notes were updated.

        Raises:
            NoteNotFoundError: If the source note does not exist.
            NoteExistsError: If a note already exists at the destination.
            FileReadError: If a note that must be read cannot be read.
            InvalidFrontmatterError: If the moved note's frontmatter is not
                valid.
            FileCreationError: If parent folders cannot be created.
            FileDeletionError: If the note cannot be moved.
            FileWriteError: If a note cannot be written after the move.
            DirectoryReadError: If a directory in the vault cannot be read.
        """
        if not self.note_exists(source):
            raise NoteNotFoundError(source.path)

        if self.note_exists(destination):
            raise NoteExistsError(destination.path)

        original_text: str = self.read_note(source)
        text: str = source.text_with_id(original_text, destination.note_id) or original_text

        self_links: int = 0
        other_updates: list[tuple[Note, str]] = []
        other_links: int = 0

        if update_links:
            others: list[Note] = [note for note in self.iter_notes() if note != source]
            replace = _link_replacer(source, destination, others)

            text, self_links = wikilinks.rewrite(text, replace)
            for other in others:
                other_text: str = self.read_note(other)
                rewritten, count = wikilinks.rewrite(other_text, replace)
                if count:
                    other_updates.append((other, rewritten))
                    other_links += count

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

        if text != original_text:
            self.write_note(destination, text)

        for done, (other, rewritten) in enumerate(other_updates):
            try:
                self.write_note(other, rewritten)
            except FileWriteError as error:
                raise FileWriteError(
                    error.path,
                    f"{error.reason or 'write failed'} "
                    f"({done} of {len(other_updates)} linking notes were updated first)",
                ) from error

        return MoveResult(
            links_updated=self_links + other_links,
            notes_updated=len(other_updates) + (1 if self_links else 0),
        )


def _link_replacer(
    source: Note, destination: Note, others: list[Note]
) -> Callable[[str], str | None]:
    """
    Builds the function that decides what each wiki link becomes in a move.

    Matching ignores case and an optional ``.md`` on the link target.

    Args:
        source: The note being moved.
        destination: The note at its new path.
        others: Every other note in the vault, used to detect shared titles.

    Returns:
        A function from a link target to its new target, or None when the
        link should stay as it is.
    """
    old_path: str = source.path.with_suffix("").as_posix().casefold()
    old_title: str = source.title.casefold()
    new_path: str = destination.path.with_suffix("").as_posix()

    old_title_shared: bool = any(note.title.casefold() == old_title for note in others)
    new_title_shared: bool = any(
        note.title.casefold() == destination.title.casefold() for note in others
    )
    source_at_root: bool = source.path.parent == Path()
    destination_at_root: bool = destination.path.parent == Path()

    def replace(target: str) -> str | None:
        has_suffix: bool = Note.is_note_name(target)
        bare: str = target[: -len(MARKDOWN_SUFFIX)] if has_suffix else target
        key: str = bare.casefold()

        if "/" in bare:
            if key != old_path:
                return None
            new_target: str = new_path
        else:
            if key != old_title:
                return None
            # A bare name is an exact path at the root, so it is only unclear
            # when the note lives in a folder and another note shares its title.
            if old_title_shared and not source_at_root:
                return None
            title_is_unique: bool = not new_title_shared or destination_at_root
            if destination.title == source.title and title_is_unique:
                return None
            new_target = destination.title if title_is_unique else new_path

        return new_target + (MARKDOWN_SUFFIX if has_suffix else "")

    return replace

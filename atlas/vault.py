# atlas/vault.py

"""The ``Vault`` object, which represents a Markdown worldbuilding vault."""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping
    from typing import Any

from atlas import frontmatter, templates, wikilinks
from atlas.errors import (
    DirectoryReadError,
    FileCreationError,
    FileDeletionError,
    FileReadError,
    FileWriteError,
    InvalidFrontmatterError,
    InvalidNoteNameError,
    InvalidTemplateNameError,
    NoteExistsError,
    NoteNotFoundError,
    NoteNotInTrashError,
    TemplateExistsError,
    TemplateNotFoundError,
    VaultAlreadyInitializedError,
    VaultNotFoundError,
    VaultNotInitializedError,
)
from atlas.note import MARKDOWN_SUFFIX, Note

ATLAS_DIRNAME: str = ".atlas"
CONFIG_FILENAME: str = "config.toml"
TRASH_DIRNAME: str = ".trash"
TRASH_STAMP_FORMAT: str = "%Y%m%d-%H%M%S"
_TRASH_STAMP_PATTERN: str = r"\d{8}-\d{6}"  # Matches TRASH_STAMP_FORMAT.
TEMPLATE_DIRNAME: str = "templates"

DEFAULT_CONFIG: str = """\
# Atlas vault configuration.
 
schema_version = 1
"""

DEFAULT_TEMPLATE: str = '---\nid: "{{id}}"\n---\n\n# {{title}}\n\n'

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

    @property
    def templates_dir(self) -> Path:
        """The path of the templates directory. It may not exist yet."""
        return self.atlas_dir / TEMPLATE_DIRNAME

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

    @staticmethod
    def _bare_template_name(name: str) -> str:
        """
        Validates a template name and removes an optional ``.md`` suffix.

        Args:
            name: The template name, such as ``Nation`` or ``Nation.md``.

        Returns:
            The name without its suffix.

        Raises:
            InvalidTemplateNameError: If the name is empty or contains a path
                separator or ``..``.
        """
        bare: str = name[: -len(MARKDOWN_SUFFIX)] if Note.is_note_name(name) else name
        if not bare.strip() or "/" in bare or "\\" in bare or ".." in bare:
            raise InvalidTemplateNameError(name, "must not be empty or contain '/', '\\', or '..'")
        return bare

    def _find_template(self, bare: str) -> Path | None:
        """
        Finds a template file by name, ignoring letter case.

        Args:
            bare: The template name without the ``.md`` suffix.

        Returns:
            The absolute path of the template, or None if there is none.
        """
        target: str = f"{bare}{MARKDOWN_SUFFIX}".casefold()
        return next(
            (
                candidate
                for candidate in self.templates_dir.glob(f"*{MARKDOWN_SUFFIX}")
                if candidate.name.casefold() == target and candidate.is_file()
            ),
            None,
        )

    def read_template(self, name: str) -> tuple[dict[str, Any], str]:
        """
        Reads and parses a template by name from the templates directory.

        The name is matched case-insensitively, and an optional ``.md`` suffix
        is ignored, so ``Nation``, ``nation`` and ``Nation.md`` are the same.

        Args:
            name: The template name, such as ``Nation``.

        Returns:
            The template's frontmatter and its body.

        Raises:
            InvalidTemplateNameError: If the name is empty or contains a path
                separator or ``..``.
            TemplateNotFoundError: If the template file does not exist.
            FileReadError: If the file cannot be read.
            InvalidFrontmatterError: If the frontmatter is malformed.
        """
        bare: str = self._bare_template_name(name)
        template_path: Path | None = self._find_template(bare)
        if template_path is None:
            raise TemplateNotFoundError(
                Path(ATLAS_DIRNAME, TEMPLATE_DIRNAME, f"{bare}{MARKDOWN_SUFFIX}")
            )

        try:
            text: str = template_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            reason: str = getattr(error, "strerror", None) or str(error)
            raise FileReadError(template_path, reason) from error

        try:
            data, body = frontmatter.split(text)
        except InvalidFrontmatterError as error:
            raise InvalidFrontmatterError(
                error.reason, template_path.relative_to(self.root)
            ) from error

        return data, body

    def create_template(self, name: str) -> Path:
        """
        Creates a new template file, and the templates directory if needed.

        The template starts with a single ``# {{title}}`` heading and no
        frontmatter. The name is checked case-insensitively against existing
        templates, so ``nation`` is refused when ``Nation.md`` exists, because
        ``read_template`` could not tell them apart.

        Args:
            name: The template name, such as ``Nation``. The ``.md`` suffix is
                optional.

        Returns:
            The absolute path of the new template.

        Raises:
            InvalidTemplateNameError: If the name is empty or contains a path
                separator or ``..``.
            TemplateExistsError: If a template with that name already exists.
            FileCreationError: If the template or the templates directory
                cannot be created.
        """
        bare: str = self._bare_template_name(name)

        existing: Path | None = self._find_template(bare)
        if existing is not None:
            raise TemplateExistsError(Path(ATLAS_DIRNAME, TEMPLATE_DIRNAME, existing.name))

        path: Path = self.templates_dir / f"{bare}{MARKDOWN_SUFFIX}"

        try:
            self.templates_dir.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise FileCreationError(self.templates_dir, error.strerror) from error

        try:
            with path.open("x", encoding="utf-8") as file:
                file.write(DEFAULT_TEMPLATE)
        except FileExistsError as error:
            raise TemplateExistsError(path.relative_to(self.root)) from error
        except OSError as error:
            raise FileCreationError(path, error.strerror) from error

        return path

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

    def resolve_folder(self, name: str) -> Path | None:
        """
        Finds an existing folder in the vault from a user-supplied name.

        A trailing separator is allowed. Folders outside the vault or inside the
        ``.atlas`` directory are not found.

        Args:
            name: The name given on the command line, relative to the vault root.

        Returns:
            The folder path relative to the vault root (``.`` for the root
            itself), or None if the name is not an existing folder in the vault.
        """
        cleaned: str = name.strip().rstrip("/\\")
        if not cleaned:
            return None

        path: Path = (self.root / cleaned).resolve()
        if not path.is_dir() or not path.is_relative_to(self.root):
            return None
        if path.is_relative_to(self.atlas_dir):
            return None

        return path.relative_to(self.root)

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

    def create(
        self,
        note: Note,
        properties: Mapping[str, Any] | None = None,
        template: str | None = None,
        note_id: str | None = None,
        body: str | None = None,
    ) -> None:
        """
        Creates the note file, along with any missing parent folders.

        Without a template, the note starts with YAML frontmatter holding its id,
        then any extra properties, followed by a top-level heading taken from its
        title. With a template, the template's frontmatter and body are used
        instead of the heading, with ``{{title}}``, ``{{id}}`` and ``{{date}}``
        filled in. The id comes from the note's path unless ``note_id`` is given,
        and ``properties`` override the template's frontmatter.

        Args:
            note: The note to create.
            properties: Extra frontmatter to write, such as ``{"type": "nation"}``.
            template: The name of a template in the vault's templates directory,
                without the ``.md`` suffix.
            note_id: An id to use instead of the one derived from the note's
                path. It is also what ``{{id}}`` becomes in a template.
            body: Text to use as the note body instead of the default heading or
                the template body. A trailing newline is added if it is missing.
                The text is written as given, so ``{{placeholders}}`` in it are not
                rendered. The template's frontmatter is still applied.

        Raises:
            InvalidTemplateNameError: If the template name is not valid.
            TemplateNotFoundError: If the template does not exist.
            FileReadError: If the template cannot be read.
            InvalidFrontmatterError: If the template's frontmatter is not valid.
            NoteExistsError: If the note already exists.
            FileCreationError: If the note or its parent folders cannot be
                created.
        """
        path: Path = self.path_of(note)
        resolved_id: str = note_id if note_id is not None else note.note_id
        data: dict[str, Any] = {"id": resolved_id}
        note_body: str = f"# {note.title}\n"

        if template is not None:
            template_data, template_body = self.read_template(template)
            values: dict[str, str] = {
                "title": note.title,
                "id": resolved_id,
                "date": datetime.now().strftime("%Y-%m-%d"),
            }
            rendered: dict[str, Any] = templates.render_data(template_data, values)
            data.update((key, value) for key, value in rendered.items() if key != "id")
            note_body = templates.render(template_body, values)

        if body is not None:
            note_body = body if not body or body.endswith("\n") else f"{body}\n"

        data.update((key, value) for key, value in (properties or {}).items() if key != "id")

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise FileCreationError(path.parent, error.strerror) from error

        try:
            with path.open("x", encoding="utf-8") as file:
                file.write(frontmatter.join(data, note_body))
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
        stamp: str = datetime.now().strftime(TRASH_STAMP_FORMAT)
        destination: Path = (
            trash_dir / note.path.parent / f"{note.path.stem}.{stamp}{note.path.suffix}"
        )

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(self.path_of(note), destination)
        except (OSError, shutil.Error) as error:
            reason = getattr(error, "strerror", None) or str(error)
            raise FileDeletionError(self.path_of(note), reason) from error

    def latest_trashed(self, note: Note) -> Path | None:
        """
        Finds the most recent trashed copy of a note.

        Deleting a note adds a timestamp to its name, so a note that was
        deleted several times has several copies in the trash. This looks for
        copies in the same trash folder that the note would have been moved to.

        Args:
            note: The note, by its original path in the vault.

        Returns:
            The absolute path of the newest trashed copy, or None if the note
            is not in the trash.

        Raises:
            DirectoryReadError: If the trash folder cannot be read.
        """
        folder: Path = self.trash_dir / note.path.parent
        pattern: re.Pattern[str] = re.compile(
            rf"{re.escape(note.path.stem)}\.(?P<stamp>{_TRASH_STAMP_PATTERN})"
            rf"{re.escape(note.path.suffix)}"
        )

        try:
            if not folder.is_dir():
                return None
            copies: list[tuple[str, Path]] = [
                (found["stamp"], entry)
                for entry in folder.iterdir()
                if entry.is_file() and (found := pattern.fullmatch(entry.name))
            ]
        except OSError as error:
            raise DirectoryReadError(folder, error.strerror) from error

        if not copies:
            return None
        return max(copies, key=lambda copy: copy[0])[1]

    def find_restorable(self, note: Note) -> Path:
        """
        Checks that a note can be restored and finds the copy to restore.

        Args:
            note: The note, by its original path in the vault.

        Returns:
            The absolute path of the trashed copy that would be restored.

        Raises:
            NoteNotInTrashError: If the note is not in the trash.
            NoteExistsError: If something already exists at the note's path.
            DirectoryReadError: If the trash folder cannot be read.
        """
        trashed: Path | None = self.latest_trashed(note)
        if trashed is None:
            raise NoteNotInTrashError(note.path)
        if self.path_of(note).exists():
            raise NoteExistsError(note.path)
        return trashed

    def restore(self, note: Note) -> None:
        """
        Moves a deleted note out of the trash and back to its original path.

        The timestamp that deletion added to the name is removed. If the note
        was deleted several times, the most recent copy is restored. Missing
        parent folders are created, and trash folders left empty are removed.
        The note is moved as it is: its id and links were not touched by
        deleting it, so there is nothing to put back.

        Args:
            note: The note, by its original path in the vault.

        Raises:
            NoteNotInTrashError: If the note is not in the trash.
            NoteExistsError: If something already exists at the note's path.
            DirectoryReadError: If the trash folder cannot be read.
            FileCreationError: If parent folders cannot be created.
            FileWriteError: If the note cannot be moved out of the trash.
        """
        trashed: Path = self.find_restorable(note)
        destination: Path = self.path_of(note)

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise FileCreationError(destination.parent, error.strerror) from error

        try:
            shutil.move(trashed, destination)
        except (OSError, shutil.Error) as error:
            reason = getattr(error, "strerror", None) or str(error)
            raise FileWriteError(destination, reason) from error

        self._prune_trash(trashed.parent)

    def _prune_trash(self, folder: Path) -> None:
        """
        Removes empty folders from the trash, from a folder up to the trash.

        The trash directory itself is kept. This stops at the first folder
        that is not empty or cannot be removed.

        Args:
            folder: The trash folder to start from.
        """
        while folder != self.trash_dir and folder.is_relative_to(self.trash_dir):
            try:
                folder.rmdir()
            except OSError:
                return
            folder = folder.parent

    def move(self, source: Note, destination: Note, update_links: bool = True) -> MoveResult:
        """
        Moves or renames a note to a new destination.

        Creates any missing parent directories for the destination. If the
        note has a default ``id`` in its frontmatter, meaning the one derived
        from its old path, the id is rewritten to match the new path. A note
        without an ``id``, or with a custom one, is moved unchanged.

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

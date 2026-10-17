# atlas/errors.py

"""Custom exceptions for ``Atlas``."""

from pathlib import Path


class AtlasError(Exception):
    """
    Base class for every error that Atlas raises on purpose.

    Catching this class handles any Atlas-specific failure without also
    swallowing unrelated exceptions, such as ``KeyboardInterrupt`` or genuine
    bugs. The message passed to the constructor is what the user sees.

    Attributes:
        exit_code: The process exit code to use when this error ends a
            command. Subclasses may override it.
    """

    exit_code: int = 1


class VaultNotFoundError(AtlasError):
    """
    Raised when the vault path does not exist.

    Attributes:
        path: The vault path that could not be found.
    """

    def __init__(self, path: Path) -> None:
        self.path: Path = path
        super().__init__(f"Vault path does not exist: {path}")


class VaultNotInitializedError(AtlasError):
    """
    Raised when a command needs an Atlas vault but none has been initialized.

    Attributes:
        path: The vault path that has no ``.atlas`` directory.
    """

    def __init__(self, path: Path) -> None:
        self.path: Path = path
        super().__init__(f"Not an Atlas vault, run 'atlas init' first: {path}")


class VaultAlreadyInitializedError(AtlasError):
    """
    Raised when initializing a vault that already has an ``.atlas`` directory.

    Attributes:
        path: The vault path that is already initialized.
    """

    def __init__(self, path: Path) -> None:
        self.path: Path = path
        super().__init__(f"Vault is already initialized: {path}")


class InvalidNoteNameError(AtlasError):
    """
    Raised when a note name cannot be turned into a valid note path.

    Attributes:
        name: The name as the user typed it.
        reason: A short explanation of why the name was rejected.
    """

    def __init__(self, name: str, reason: str) -> None:
        self.name: str = name
        self.reason: str = reason
        super().__init__(f"Invalid note name {name!r}: {reason}")


class NoteExistsError(AtlasError):
    """
    Raised when creating a note whose file already exists.

    Attributes:
        path: The path of the existing note, relative to the vault root.
    """

    def __init__(self, path: Path) -> None:
        self.path: Path = path
        super().__init__(f"Note already exists: {path}")


class NoteNotFoundError(AtlasError):
    """
    Raised when a note that must exist does not.

    Attributes:
        path: The path of the missing note, relative to the vault root.
    """

    def __init__(self, path: Path) -> None:
        self.path: Path = path
        super().__init__(f"Note does not exist: {path}")


class FileDeletionError(AtlasError):
    """
    Raised when a file cannot be deleted.

    Attributes:
        path: The file that could not be deleted.
        reason: The underlying operating system message, if there was one.
    """

    def __init__(self, path: Path, reason: str | None = None) -> None:
        self.path: Path = path
        self.reason: str | None = reason
        message: str = f"Failed to delete {path}"
        if reason:
            message += f": {reason}"
        super().__init__(message)


class FileCreationError(AtlasError):
    """
    Raised when a file or directory cannot be created.

    Attributes:
        path: The file or directory that could not be created.
        reason: The underlying operating system message, if there was one.
    """

    def __init__(self, path: Path, reason: str | None = None) -> None:
        self.path: Path = path
        self.reason: str | None = reason
        message: str = f"Failed to create {path}"
        if reason:
            message += f": {reason}"
        super().__init__(message)


class DirectoryReadError(AtlasError):
    """
    Raised when a directory cannot be read.

    Attributes:
        path: The directory that could not be read.
        reason: The underlying operating system message, if there was one.
    """

    def __init__(self, path: Path, reason: str | None = None) -> None:
        self.path: Path = path
        self.reason: str | None = reason
        message: str = f"Failed to read directory {path}"
        if reason:
            message += f": {reason}"
        super().__init__(message)


class NotAFolderError(AtlasError):
    """
    Raised when several notes are moved to a destination that is not a directory.

    Attributes:
        name: The destination as the user typed it.
    """

    def __init__(self, name: str) -> None:
        self.name: str = name
        super().__init__(f"Target is not an existing directory: {name!r}")


class DuplicateDestinationError(AtlasError):
    """
    Raised when two moved notes would end up at the same path.

    Attributes:
        path: The path that more than one note would take.
    """

    def __init__(self, path: Path) -> None:
        self.path: Path = path
        super().__init__(f"More than one note would be moved to: {path}")


class FileReadError(AtlasError):
    """
    Raised when a file cannot be read.

    Attributes:
        path: The file that could not be read.
        reason: The underlying operating system message, if there was one.
    """

    def __init__(self, path: Path, reason: str | None = None) -> None:
        self.path: Path = path
        self.reason: str | None = reason
        message: str = f"Failed to read {path}"
        if reason:
            message += f": {reason}"
        super().__init__(message)


class FileWriteError(AtlasError):
    """
    Raised when a file cannot be written.

    Attributes:
        path: The file that could not be written.
        reason: The underlying operating system message, if there was one.
    """

    def __init__(self, path: Path, reason: str | None = None) -> None:
        self.path: Path = path
        self.reason: str | None = reason
        message: str = f"Failed to write {path}"
        if reason:
            message += f": {reason}"
        super().__init__(message)


class InvalidFrontmatterError(AtlasError):
    """
    Raised when a note's YAML frontmatter cannot be understood.

    Attributes:
        reason: A short explanation of what is wrong with the frontmatter.
        path: The note the frontmatter belongs to, if it is known.
    """

    def __init__(self, reason: str, path: Path | None = None) -> None:
        self.reason: str = reason
        self.path: Path | None = path
        location: str = f" in {path}" if path else ""
        super().__init__(f"Invalid frontmatter{location}: {reason}")


class InvalidNoteIdError(AtlasError):
    """
    Raised when a custom note id cannot be used.

    Attributes:
        note_id: The id as the user typed it.
        reason: A short explanation of why the id was rejected.
    """

    def __init__(self, note_id: str, reason: str) -> None:
        self.note_id: str = note_id
        self.reason: str = reason
        super().__init__(f"Invalid note id {note_id!r}: {reason}")


class InvalidPropertyError(AtlasError):
    """
    Raised when a ``KEY=VALUE`` frontmatter property cannot be understood.

    Attributes:
        assignment: The property as the user typed it.
        reason: A short explanation of why it was rejected.
    """

    def __init__(self, assignment: str, reason: str) -> None:
        self.assignment: str = assignment
        self.reason: str = reason
        super().__init__(f"Invalid property {assignment!r}: {reason}")


class InvalidTemplateNameError(AtlasError):
    """
    Raised when a template name cannot be used to look up a template.

    Attributes:
        name: The name as the user typed it.
        reason: A short explanation of why the name was rejected.
    """

    def __init__(self, name: str, reason: str) -> None:
        self.name: str = name
        self.reason: str = reason
        super().__init__(f"Invalid template name {name!r}: {reason}")


class TemplateNotFoundError(AtlasError):
    """
    Raised when a template cannot be found.

    Attributes:
        path: The path of the missing template, relative to the vault root.
    """

    def __init__(self, path: Path) -> None:
        self.path: Path = path
        super().__init__(f"Template does not exist: {path}")

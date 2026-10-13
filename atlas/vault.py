# atlas/vault.py

"""The ``Vault`` object, which represents a Markdown worldbuilding vault."""

from pathlib import Path

from atlas.errors import (
    FileCreationError,
    VaultAlreadyInitializedError,
    VaultNotFoundError,
    VaultNotInitializedError,
)

ATLAS_DIRNAME: str = ".atlas"
CONFIG_FILENAME: str = "config.toml"
MARKDOWN_SUFFIX: str = ".md"
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
    root path, its ``.atlas`` directory, and the rules for turning note names
    into paths inside it. Creating a ``Vault`` never touches the file system,
    so it is safe to build one for a path that does not exist yet.

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
    def open(cls, root: Path | str | None = None) -> "Vault":
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
    ) -> "Vault":
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

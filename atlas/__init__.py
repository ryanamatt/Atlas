# atlas/__init__.py

"""
Atlas: a command-line tool for managing and validating worldbuilding vaults.

Attributes:
    __version__: The installed version of Atlas, read from package metadata.
        Falls back to a development version when Atlas is not installed.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__: str = version("atlas")
except PackageNotFoundError:
    __version__: str = "0.1.0-dev"

__all__ = ["__version__"]

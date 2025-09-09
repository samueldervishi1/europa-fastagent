"""
Version information for FastAgent Ultimate MCP Coordinator

This file dynamically reads version from pyproject.toml to avoid duplication.
"""

import tomllib
from pathlib import Path

def _get_version_from_pyproject():
    """Read version from pyproject.toml"""
    try:
        pyproject_path = Path(__file__).parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        return data["project"]["version"]
    except Exception:
        return "0.0.0"

__version__ = _get_version_from_pyproject()

VERSION = __version__

# Parse version components
version_parts = __version__.split(".")
VERSION_MAJOR = int(version_parts[0]) if len(version_parts) > 0 else 0
VERSION_MINOR = int(version_parts[1]) if len(version_parts) > 1 else 0  
VERSION_PATCH = int(version_parts[2]) if len(version_parts) > 2 else 0

VERSION_TUPLE = (VERSION_MAJOR, VERSION_MINOR, VERSION_PATCH)

def get_version():
    """Return the version as a string."""
    return __version__

def get_version_tuple():
    """Return the version as a tuple of (major, minor, patch)."""
    return VERSION_TUPLE 
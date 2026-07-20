"""Server version.

Single source is `pyproject.toml` (`[project] version`). At runtime we read it
from the installed package metadata, so there is exactly one place to bump on a
release (see the release runbook). `/health` and the FastAPI app report this.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version as _dist_version

try:
    __version__ = _dist_version("server")
except PackageNotFoundError:  # running from source without an install
    __version__ = "0+unknown"

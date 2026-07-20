"""Single source of truth for the server version.

Bumped per dotmage-spec/RELEASING.md. `pyproject.toml` derives its version from
this attribute (dynamic version), and `/health` reports it — so there is exactly
one place to change on a release.
"""

from __future__ import annotations

__version__ = "2.0.0"

"""Read-only FilamentManager MCP server."""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_repo_root_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    if (repo_root / "integrations" / "ai" / "shared").exists() and str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


_ensure_repo_root_on_path()

__version__ = "0.1.0"

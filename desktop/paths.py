"""Desktop entry helpers — re-exports freeze-aware paths from the backend package."""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.paths import frontend_dist, is_frozen, resource_root, user_data_dir  # noqa: E402

__all__ = ["frontend_dist", "is_frozen", "resource_root", "user_data_dir"]

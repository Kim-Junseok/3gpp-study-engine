from __future__ import annotations

import os
from pathlib import Path


def data_root(explicit: Path | str | None = None) -> Path:
    """Resolve runtime research storage without moving existing data."""
    return Path(explicit or os.environ.get("THREEGPP_DATA_ROOT", "data")).expanduser()

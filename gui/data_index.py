from __future__ import annotations

from pathlib import Path
from typing import Any

def file_list_for_step(data_files: dict[str, Any], step: str) -> list[Path]:
    """
    Return a list of files for a dropdown-based step.
    """
    v = data_files.get(step, [])
    if v is None:
        return []
    if isinstance(v, list):
        return v
    # label-based steps store a single Path
    return [v]

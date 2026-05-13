# grid_calibration/gui/workflow/io_helpers.py

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import numpy as np

from ...errors import MissingProductError, ProductLoadError, ProductSaveError


def require_existing_file(path: Path, *, label: str = "product") -> Path:
    """
    Return ``path`` if it exists, otherwise raise ``MissingProductError``.
    """
    path = Path(path)

    if not path.exists():
        raise MissingProductError(f"Missing {label}: {path}")

    return path


def ensure_parent_dir(path: Path) -> Path:
    """
    Ensure that the parent directory of ``path`` exists.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def validate_load_keys(
    path: Path,
    keys: Iterable[str],
    required_keys: Iterable[str],
    *,
    label: str = "product",
) -> None:
    """
    Validate that an NPZ file contains the required keys.
    """
    missing = sorted(set(required_keys) - set(keys))

    if missing:
        raise ProductLoadError(
            f"{label} {path} is missing required NPZ keys: "
            f"{', '.join(missing)}"
        )

def validate_save_keys(
    provided_keys: Iterable[str],
    required_keys: Iterable[str],
    *,
    optional_keys: Iterable[str] = (),
    label: str = "product",
) -> None:
    """
    Validate that the keys being saved match the declared schema.

    Raises
    ------
    ProductSaveError
        If required keys are missing or unexpected keys are present.
    """
    provided = set(provided_keys)
    required = set(required_keys)
    optional = set(optional_keys)

    missing = sorted(required - provided)
    unexpected = sorted(provided - required - optional)

    messages = []

    if missing:
        messages.append(
            f"missing required keys: {', '.join(missing)}"
        )

    if unexpected:
        messages.append(
            f"unexpected keys: {', '.join(unexpected)}"
        )

    if messages:
        raise ProductSaveError(
            f"Invalid {label} schema: " + "; ".join(messages)
        )

def load_npz_dict(
    path: Path,
    required_keys: Iterable[str],
    *,
    optional_keys: Iterable[str] = (),
    allow_pickle: bool = False,
    label: str = "product",
) -> dict[str, Any]:
    """
    Load selected keys from an NPZ file into a dictionary.
    """
    path = require_existing_file(path, label=label)
    required_keys = tuple(required_keys)
    optional_keys = tuple(optional_keys)

    try:
        with np.load(path, allow_pickle=allow_pickle) as data:
            validate_load_keys(
                path,
                data.files,
                required_keys,
                label=label,
            )

            loaded: dict[str, Any] = {
                key: data[key]
                for key in required_keys
            }

            loaded.update(
                {
                    key: data[key]
                    for key in optional_keys
                    if key in data.files
                }
            )

    except ProductLoadError:
        raise
    except Exception as exc:
        raise ProductLoadError(f"Failed to load {label}: {path}") from exc

    return loaded


def save_npz_dict(
    path: Path,
    *,
    required_keys: Iterable[str] | None = None,
    optional_keys: Iterable[str] = (),
    label: str = "product",
    compressed: bool = True,
    **arrays: Any,
) -> None:
    """
    Save arrays/objects to an NPZ file.
    """
    path = ensure_parent_dir(path)

    if required_keys is not None:
        validate_save_keys(
            arrays.keys(),
            required_keys,
            optional_keys=optional_keys,
            label=label,
        )

    try:
        if compressed:
            np.savez_compressed(path, **arrays)
        else:
            np.savez(path, **arrays)

    except Exception as exc:
        raise ProductSaveError(f"Failed to save {label}: {path}") from exc


def object_array(value: Any) -> np.ndarray:
    """
    Store arbitrary Python objects safely in an object array.
    """
    return np.array(value, dtype=object)


def maybe_item(value: Any) -> Any:
    """
    Convert a 0-d numpy object array/scalar to the contained Python object.
    """
    if hasattr(value, "shape") and value.shape == ():
        return value.item()

    return value
# grid_calibration/gui/workflow/io_helpers.py
"""
Low-level helpers for loading, saving, and validating NPZ product files.

The :mod:`grid_calibration.gui.workflow.io_helpers` module contains the
filesystem and schema-validation primitives used by
:class:`~grid_calibration.gui.workflow.product_io.ProductIO`.  The helpers in
this module intentionally know nothing about pipeline steps, sessions, or
workflow order.  They only enforce local file-level contracts:

* required product files must exist before loading;
* required NPZ keys must be present;
* unexpected keys must not be written when a schema is declared;
* parent directories are created before saving; and
* lower-level NumPy exceptions are converted into package-specific errors.

Keeping these utilities separate from
:class:`~grid_calibration.gui.workflow.product_io.ProductIO` makes the product
system easier to test.  ProductIO owns step-aware behavior such as product
naming, registration, singleton/per-input semantics, caching, and encode/decode
hooks.  This module owns the generic NPZ mechanics underneath that interface.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import numpy as np

from ...errors import MissingProductError, ProductLoadError, ProductSaveError


def require_existing_file(path: Path, *, label: str = "product") -> Path:
    """
    Return a path after verifying that it exists on disk.

    Parameters
    ----------
    path : :class:`pathlib.Path`
        File path that is expected to exist.
    label : :class:`str`, optional
        Human-readable label used in the error message.  This is usually a
        product description supplied by
        :class:`~grid_calibration.gui.workflow.product_io.ProductIO`.

    Returns
    -------
    :class:`pathlib.Path`
        The normalized file path.

    Raises
    ------
    :class:`~grid_calibration.errors.MissingProductError`
        If ``path`` does not exist.
    """
    path = Path(path)

    if not path.exists():
        raise MissingProductError(f"Missing {label}: {path}")

    return path


def ensure_parent_dir(path: Path) -> Path:
    """
    Ensure that the parent directory for a path exists.

    Parameters
    ----------
    path : :class:`pathlib.Path`
        File path whose parent directory should be created.

    Returns
    -------
    :class:`pathlib.Path`
        The normalized file path.  The file itself is not created by this
        function.
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
    Validate that a loaded NPZ file contains all required keys.

    Parameters
    ----------
    path : :class:`pathlib.Path`
        Path to the NPZ file being validated.  The path is used only for error
        reporting.
    keys : iterable of :class:`str`
        Keys found in the loaded file, usually ``data.files`` from
        :func:`numpy.load`.
    required_keys : iterable of :class:`str`
        Keys that must be present for the product to be considered valid.
    label : :class:`str`, optional
        Human-readable product label used in error messages.

    Returns
    -------
    :class:`None`
        This function returns ``None`` when validation succeeds.

    Raises
    ------
    :class:`~grid_calibration.errors.ProductLoadError`
        If any required key is missing.
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
    Validate keys before writing an NPZ product.

    The save schema is intentionally strict.  Every required key must be
    present, and every provided key must be declared as either required or
    optional.  This catches misspelled product fields early, before downstream
    steps try to load a malformed product.

    Parameters
    ----------
    provided_keys : iterable of :class:`str`
        Keys that will be written to disk.
    required_keys : iterable of :class:`str`
        Keys that must be present.
    optional_keys : iterable of :class:`str`, optional
        Keys that may be present but are not required.
    label : :class:`str`, optional
        Human-readable product label used in error messages.

    Returns
    -------
    :class:`None`
        This function returns ``None`` when validation succeeds.

    Raises
    ------
    :class:`~grid_calibration.errors.ProductSaveError`
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

    This helper is the loading backend for
    :meth:`~grid_calibration.gui.workflow.product_io.ProductIO.load`.  It first
    verifies that the file exists, then loads the NPZ file with
    :func:`numpy.load`, validates required keys, and returns only the declared
    required and optional keys.  Optional keys are included only when present.

    Parameters
    ----------
    path : :class:`pathlib.Path`
        NPZ file to load.
    required_keys : iterable of :class:`str`
        Keys that must exist in the file.
    optional_keys : iterable of :class:`str`, optional
        Keys that may be loaded if present.
    allow_pickle : :class:`bool`, optional
        Forwarded to :func:`numpy.load`.  Products containing object arrays must
        opt into this explicitly through
        :class:`~grid_calibration.gui.workflow.product_io.ProductIO`.
    label : :class:`str`, optional
        Human-readable product label used in error messages.

    Returns
    -------
    :class:`dict`
        Dictionary mapping declared NPZ keys to loaded arrays or objects.

    Raises
    ------
    :class:`~grid_calibration.errors.MissingProductError`
        If ``path`` does not exist.
    :class:`~grid_calibration.errors.ProductLoadError`
        If required keys are missing or NumPy fails to load the file.
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
    Save arrays or objects to an NPZ file.

    This helper is the saving backend for
    :meth:`~grid_calibration.gui.workflow.product_io.ProductIO.save`.  When a
    schema is provided through ``required_keys``, the keys are validated before
    writing.  The parent directory is created automatically.

    Parameters
    ----------
    path : :class:`pathlib.Path`
        Output NPZ file path.
    required_keys : iterable of :class:`str` or :class:`None`, optional
        Keys that must be present in ``arrays``.  If ``None``, schema validation
        is skipped.
    optional_keys : iterable of :class:`str`, optional
        Additional keys allowed in ``arrays`` when ``required_keys`` is not
        ``None``.
    label : :class:`str`, optional
        Human-readable product label used in error messages.
    compressed : :class:`bool`, optional
        If ``True``, write with :func:`numpy.savez_compressed`; otherwise write
        with :func:`numpy.savez`.
    **arrays : :class:`typing.Any`
        Named arrays or Python objects to write to the NPZ file.

    Returns
    -------
    :class:`None`
        This function writes the file and returns ``None``.

    Raises
    ------
    :class:`~grid_calibration.errors.ProductSaveError`
        If schema validation fails or NumPy fails to write the file.
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
    Convert a Python object to a NumPy object array for NPZ storage.

    This is useful for semantic products that store dictionaries, lists of
    dictionaries, or other Python objects after an encode step.  Loading such
    products requires ``allow_pickle=True`` in the corresponding
    :class:`~grid_calibration.gui.workflow.product_io.ProductIO`.

    Parameters
    ----------
    value : :class:`typing.Any`
        Python value to store.

    Returns
    -------
    :class:`numpy.ndarray`
        Object-dtype NumPy array containing ``value``.
    """
    return np.array(value, dtype=object)


def maybe_item(value: Any) -> Any:
    """
    Unwrap a scalar NumPy object array when appropriate.

    NumPy stores a dictionary or other single Python object in an NPZ file as a
    zero-dimensional object array.  This helper converts such values back to the
    contained Python object while leaving non-scalar arrays unchanged.

    Parameters
    ----------
    value : :class:`typing.Any`
        Value loaded from an NPZ file.

    Returns
    -------
    :class:`typing.Any`
        ``value.item()`` when ``value`` is a scalar NumPy array-like object;
        otherwise ``value`` unchanged.
    """
    if hasattr(value, "shape") and value.shape == ():
        return value.item()

    return value

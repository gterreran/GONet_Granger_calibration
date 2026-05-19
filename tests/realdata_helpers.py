from __future__ import annotations

import glob
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import pytest

from grid_calibration.gui.session import CalibrationSession
from grid_calibration.gui.workflow.product_io import ProductIO, ProductKind

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".tif", ".tiff")


@dataclass(frozen=True)
class RealDataConfig:
    raw_files: list[Path]
    output_dir: Path | None
    max_files: int
    run_pipeline: bool


def _truthy(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _image_files_under(directory: Path) -> list[Path]:
    files: list[Path] = []
    for ext in IMAGE_EXTENSIONS:
        files.extend(directory.glob(f"*{ext}"))
        files.extend(directory.glob(f"*{ext.upper()}"))
    return sorted(path.resolve() for path in files if path.is_file())


def _expand_globs(patterns: Iterable[str]) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        for match in glob.glob(os.path.expanduser(pattern)):
            path = Path(match).resolve()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                files.append(path)
    return sorted(set(files))


def _optional_path(value: str | None) -> Path | None:
    if not value:
        return None
    return Path(value).expanduser().resolve()


def get_realdata_config() -> RealDataConfig:
    """
    Return real-data test configuration from environment variables.

    Supported variables
    -------------------
    GRID_CALIBRATION_REALDATA_GLOB
        One or more image glob patterns, separated by ``os.pathsep``.
    GRID_CALIBRATION_REALDATA_DIR
        Directory containing real input images. Used when no glob is supplied.
    GRID_CALIBRATION_REALDATA_OUTDIR
        Optional directory containing existing pipeline products.
    GRID_CALIBRATION_REALDATA_MAX_FILES
        Maximum number of raw files used by optional tests. Defaults to 5.
    GRID_CALIBRATION_RUN_REAL_PIPELINE
        Set to 1/true/yes/on to run slow processing tests.
    """
    max_files = int(os.environ.get("GRID_CALIBRATION_REALDATA_MAX_FILES", "5"))

    glob_spec = os.environ.get("GRID_CALIBRATION_REALDATA_GLOB")
    if glob_spec:
        raw_files = _expand_globs(glob_spec.split(os.pathsep))
    else:
        data_dir = os.environ.get("GRID_CALIBRATION_REALDATA_DIR")
        if not data_dir:
            pytest.skip(
                "Set GRID_CALIBRATION_REALDATA_GLOB or GRID_CALIBRATION_REALDATA_DIR "
                "to run optional real-data tests."
            )
        raw_files = _image_files_under(Path(data_dir).expanduser())

    if not raw_files:
        pytest.skip("Real-data configuration did not match any input image files.")

    return RealDataConfig(
        raw_files=raw_files[:max_files],
        output_dir=_optional_path(os.environ.get("GRID_CALIBRATION_REALDATA_OUTDIR")),
        max_files=max_files,
        run_pipeline=_truthy(os.environ.get("GRID_CALIBRATION_RUN_REAL_PIPELINE")),
    )


def product_status_rows(
    *,
    session: CalibrationSession,
    product_io_by_step: dict[str, ProductIO | None],
) -> list[dict[str, Any]]:
    """
    Return discovery/load status rows for all registered products.
    """
    rows: list[dict[str, Any]] = []

    for step_key, product in product_io_by_step.items():
        if product is None:
            continue

        discovered = session.get(step_key)
        row: dict[str, Any] = {
            "step": step_key,
            "kind": product.kind.name.lower(),
            "count": 0,
            "expected": None,
            "loadable": False,
            "paths": [],
            "error": "",
        }

        try:
            if product.kind is ProductKind.PER_INPUT:
                paths = [Path(p) for p in (discovered or [])]
                row["paths"] = paths
                row["count"] = len(paths)
                row["expected"] = len(session.raw_files)
                if paths:
                    product.load(paths[0])
                    row["loadable"] = True
            else:
                path = None if discovered is None else Path(discovered)
                row["paths"] = [] if path is None else [path]
                row["count"] = 0 if path is None else 1
                row["expected"] = 1
                if path is not None:
                    product.load(path)
                    row["loadable"] = True
        except Exception as exc:  # pragma: no cover - reported by assertion message.
            row["error"] = f"{type(exc).__name__}: {exc}"

        rows.append(row)

    return rows


def format_product_status(rows: list[dict[str, Any]]) -> str:
    """
    Format product discovery/load status rows for pytest output.
    """
    lines = ["", "Real-data product status:"]
    for row in rows:
        expected = row["expected"]
        expected_text = "?" if expected is None else str(expected)
        status = "loadable" if row["loadable"] else "missing"
        if row["error"]:
            status = row["error"]
        lines.append(
            f"  - {row['step']:<20} {row['kind']:<9} "
            f"{row['count']}/{expected_text:<3} {status}"
        )
        for path in row["paths"][:3]:
            lines.append(f"      {path}")
        if len(row["paths"]) > 3:
            lines.append(f"      ... {len(row['paths']) - 3} more")
    return "\n".join(lines)


def requested_required_steps(config) -> set[str]:
    """
    Return product step keys requested via pytest option or environment.
    """
    option_value = config.getoption("--realdata-require-products", default=None)
    env_value = os.environ.get("GRID_CALIBRATION_REQUIRE_REALDATA_PRODUCTS")
    requested = option_value or env_value
    if not requested:
        return set()
    requested = requested.strip()
    if requested.lower() == "all":
        return {"all"}
    return {part.strip() for part in requested.split(",") if part.strip()}


def realdata_option_number(config, name: str, env_name: str, default: float) -> float:
    """
    Return a numeric real-data quality threshold from pytest option or environment.
    """
    value = config.getoption(name, default=None)
    if value is None:
        value = os.environ.get(env_name)
    if value is None:
        return default
    return float(value)


def existing_realdata_session() -> CalibrationSession:
    """
    Return a session configured against an existing real-data output directory.

    The caller is skipped when the required environment is not configured, keeping
    the normal and marker-selected test suites safe to run without local data.
    """
    config = get_realdata_config()
    if config.output_dir is None:
        pytest.skip("Set GRID_CALIBRATION_REALDATA_OUTDIR to run real-data quality checks.")
    if not config.output_dir.exists():
        pytest.skip(f"Configured output directory does not exist: {config.output_dir}")
    return CalibrationSession.from_inputs(
        raw_files=config.raw_files,
        output_dir=config.output_dir,
    )


def load_existing_product(session: CalibrationSession, step_key: str) -> Any:
    """
    Load an existing product for ``step_key`` from ``session``.

    For per-input products, all discovered products are loaded and returned as a
    list. For singleton products, the loaded product dictionary is returned.
    """
    from grid_calibration.gui.workflow.registry import PRODUCT_IO_BY_STEP

    product = PRODUCT_IO_BY_STEP[step_key]
    if product is None:
        raise AssertionError(f"Step {step_key!r} has no product_io.")

    discovered = session.get(step_key)
    if product.kind is ProductKind.PER_INPUT:
        paths = [Path(path) for path in (discovered or [])]
        if not paths:
            pytest.skip(f"No existing real-data product found for {step_key!r}.")
        return [product.load(path) for path in paths]

    if discovered is None:
        pytest.skip(f"No existing real-data product found for {step_key!r}.")
    return product.load(Path(discovered))


def object_records(value: Any) -> list[Any]:
    """
    Normalize decoded object/list/array record containers into a plain list.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if hasattr(value, "tolist"):
        as_list = value.tolist()
        return as_list if isinstance(as_list, list) else [as_list]
    return [value]


def nested_getattr_or_key(value: Any, path: str) -> Any:
    """
    Return a nested attribute/dictionary value, or ``None`` if unavailable.
    """
    current = value
    for part in path.split("."):
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
    return current


def extract_model_rms(fit_result: Any) -> float | None:
    """
    Extract a representative final RMS value from a decoded modeling product.
    """
    candidates = (
        "summary_full_inliers.rms",
        "summary_full.rms",
        "rms",
        "final_rms",
        "diagnostics.final_rms",
    )
    for path in candidates:
        value = nested_getattr_or_key(fit_result, path)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return None

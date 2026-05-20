from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from grid_calibration.gui.steps.averaged_grid.keys import COUNTS_KEY, GRID_KEY as AVERAGED_GRID_KEY
from grid_calibration.gui.steps.bootstrapping_grid.keys import DATA_KEY as BOOTSTRAP_DATA_KEY
from grid_calibration.gui.steps.grid_points.keys import GRID_KEY as GRID_POINTS_KEY
from grid_calibration.gui.steps.modeling_results.keys import DATA_KEY as MODEL_DATA_KEY
from grid_calibration.gui.steps.nominal_grid.keys import DATA_KEY as NOMINAL_DATA_KEY
from grid_calibration.gui.steps.unwrapped_grid.keys import IDX_KEY, POINTS_KEY, R_KEY, THETA_KEY

from .realdata_helpers import (
    existing_realdata_session,
    extract_model_rms,
    load_existing_product,
    object_records,
    realdata_option_number,
)


pytestmark = pytest.mark.realdata


def _assert_xy_grid(value: Any, *, name: str, min_points: int) -> np.ndarray:
    grid = np.asarray(value)
    assert grid.ndim == 2, f"{name} must be a 2D array, got shape {grid.shape}."
    assert grid.shape[1] == 2, f"{name} must have shape (N, 2), got {grid.shape}."
    assert grid.shape[0] >= min_points, (
        f"{name} has too few points: {grid.shape[0]} < {min_points}."
    )
    assert np.all(np.isfinite(grid)), f"{name} contains non-finite coordinates."
    return grid


def _record_value(record: Any, key: str) -> Any:
    if isinstance(record, dict):
        return record.get(key)
    return getattr(record, key, None)


def test_realdata_grid_point_products_are_plausible(request) -> None:
    session = existing_realdata_session()
    min_points = int(
        realdata_option_number(
            request.config,
            "--realdata-min-grid-points",
            "GRID_CALIBRATION_REALDATA_MIN_GRID_POINTS",
            10,
        )
    )

    products = load_existing_product(session, "grid-points")
    assert len(products) == len(session.raw_files)

    counts: list[int] = []
    for i, product in enumerate(products):
        grid = _assert_xy_grid(
            product[GRID_POINTS_KEY],
            name=f"grid-points product {i}",
            min_points=min_points,
        )
        counts.append(grid.shape[0])

    assert min(counts) >= min_points


def test_realdata_averaged_grid_product_is_plausible(request) -> None:
    session = existing_realdata_session()
    min_points = int(
        realdata_option_number(
            request.config,
            "--realdata-min-averaged-points",
            "GRID_CALIBRATION_REALDATA_MIN_AVERAGED_POINTS",
            10,
        )
    )

    product = load_existing_product(session, "averaged-grid")
    grid = _assert_xy_grid(
        product[AVERAGED_GRID_KEY],
        name="averaged-grid product",
        min_points=min_points,
    )

    counts = np.asarray(product[COUNTS_KEY])
    assert counts.ndim == 1, f"averaged-grid counts must be 1D, got {counts.shape}."
    assert counts.shape[0] == grid.shape[0], (
        "averaged-grid counts must have one value per averaged point."
    )
    assert np.all(counts >= 1), "averaged-grid counts must be positive."


def test_realdata_unwrapped_grid_product_is_plausible(request) -> None:
    session = existing_realdata_session()
    min_points = int(
        realdata_option_number(
            request.config,
            "--realdata-min-averaged-points",
            "GRID_CALIBRATION_REALDATA_MIN_AVERAGED_POINTS",
            10,
        )
    )

    product = load_existing_product(session, "unwrapped-grid")
    points = _assert_xy_grid(
        product[POINTS_KEY],
        name="unwrapped-grid points",
        min_points=min_points,
    )
    idx = np.asarray(product[IDX_KEY])
    theta = np.asarray(product[THETA_KEY])
    radius = np.asarray(product[R_KEY])

    assert idx.shape == theta.shape == radius.shape == (points.shape[0],)
    assert np.all(np.isfinite(theta)), "unwrapped-grid theta contains non-finite values."
    assert np.all(np.isfinite(radius)), "unwrapped-grid r contains non-finite values."
    assert np.nanmin(theta) >= 0.0
    assert np.nanmax(theta) <= 360.0
    assert np.nanmin(radius) >= 0.0


def test_realdata_nominal_grid_records_are_plausible(request) -> None:
    session = existing_realdata_session()
    min_records = int(
        realdata_option_number(
            request.config,
            "--realdata-min-nominal-records",
            "GRID_CALIBRATION_REALDATA_MIN_NOMINAL_RECORDS",
            10,
        )
    )

    product = load_existing_product(session, "nominal-grid")
    records = object_records(product[NOMINAL_DATA_KEY])
    assert len(records) >= min_records

    required_fields = {"idx", "pixel_x", "pixel_y", "nominal_r", "nominal_theta"}
    missing = [
        field
        for field in required_fields
        if any(_record_value(record, field) is None for record in records[: min(25, len(records))])
    ]
    assert not missing, f"nominal-grid records are missing required fields: {missing}"

    nominal_r = np.array([_record_value(record, "nominal_r") for record in records], dtype=float)
    nominal_theta = np.array([_record_value(record, "nominal_theta") for record in records], dtype=float)
    assert np.all(np.isfinite(nominal_r))
    assert np.all(np.isfinite(nominal_theta))
    assert np.nanmin(nominal_r) >= 0.0
    assert np.nanmin(nominal_theta) >= 0.0
    assert np.nanmax(nominal_theta) <= 360.0


def test_realdata_bootstrapped_grid_records_are_plausible(request) -> None:
    session = existing_realdata_session()
    min_records = int(
        realdata_option_number(
            request.config,
            "--realdata-min-nominal-records",
            "GRID_CALIBRATION_REALDATA_MIN_NOMINAL_RECORDS",
            10,
        )
    )

    product = load_existing_product(session, "bootstrapping-grid")
    records = object_records(product[BOOTSTRAP_DATA_KEY])
    assert len(records) >= min_records

    nominal_r = np.array([_record_value(record, "nominal_r") for record in records], dtype=float)
    nominal_theta = np.array([_record_value(record, "nominal_theta") for record in records], dtype=float)
    assert np.all(np.isfinite(nominal_r))
    assert np.all(np.isfinite(nominal_theta))
    assert np.nanmin(nominal_r) >= 0.0
    assert np.nanmin(nominal_theta) >= 0.0
    assert np.nanmax(nominal_theta) <= 360.0


def test_realdata_modeling_result_quality_is_plausible(request) -> None:
    session = existing_realdata_session()
    max_rms = realdata_option_number(
        request.config,
        "--realdata-max-model-rms",
        "GRID_CALIBRATION_REALDATA_MAX_MODEL_RMS",
        50.0,
    )

    product = load_existing_product(session, "modeling-results")
    fit_result = product[MODEL_DATA_KEY]
    rms = extract_model_rms(fit_result)

    assert rms is not None, (
        "Could not extract final RMS from modeling-results product. "
        "Expected one of summary_full_inliers.rms, summary_full.rms, rms, "
        "final_rms, or diagnostics.final_rms."
    )
    assert np.isfinite(rms)
    assert rms <= max_rms, f"Model RMS is too large: {rms:.3f} > {max_rms:.3f} px."

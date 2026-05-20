from __future__ import annotations

from pathlib import Path

import pytest

from grid_calibration.gui.session import CalibrationSession
from grid_calibration.gui.workflow.product_io import ProductKind
from grid_calibration.gui.workflow.registry import ORDERED_STEP_SPECS, PRODUCT_IO_BY_STEP

from .realdata_helpers import (
    format_product_status,
    get_realdata_config,
    product_status_rows,
    requested_required_steps,
)


pytestmark = pytest.mark.realdata


def test_realdata_session_initializes_from_configured_inputs(tmp_path: Path) -> None:
    config = get_realdata_config()
    output_dir = config.output_dir or tmp_path / "grid_calibration_output"
    output_dir.mkdir(parents=True, exist_ok=True)

    session = CalibrationSession.from_inputs(
        raw_files=config.raw_files,
        output_dir=output_dir,
    )

    assert session.raw_files == config.raw_files
    assert session.output_dir == output_dir
    assert session.get("raw-image") == config.raw_files

    for step_key, product in PRODUCT_IO_BY_STEP.items():
        if product is None:
            continue
        if product.kind is ProductKind.PER_INPUT:
            assert isinstance(session.get(step_key), list)
        else:
            assert session.get(step_key) is None or isinstance(session.get(step_key), Path)


def test_realdata_existing_products_load_when_outdir_is_configured(request) -> None:
    config = get_realdata_config()
    if config.output_dir is None:
        pytest.skip("Set GRID_CALIBRATION_REALDATA_OUTDIR to validate existing real-data products.")
    if not config.output_dir.exists():
        pytest.skip(f"Configured output directory does not exist: {config.output_dir}")

    session = CalibrationSession.from_inputs(
        raw_files=config.raw_files,
        output_dir=config.output_dir,
    )

    rows = product_status_rows(
        session=session,
        product_io_by_step=PRODUCT_IO_BY_STEP,
    )
    summary = format_product_status(rows)

    if request.config.getoption("--realdata-report", default=False):
        print(summary)

    loaded_rows = [row for row in rows if row["loadable"]]
    if not loaded_rows:
        pytest.skip(
            "No existing products were discovered in GRID_CALIBRATION_REALDATA_OUTDIR."
            f"{summary}"
        )

    assert not [row for row in loaded_rows if row["error"]], summary


def test_realdata_required_products_exist_when_requested(request) -> None:
    required_steps = requested_required_steps(request.config)
    if not required_steps:
        pytest.skip(
            "Use --realdata-require-products=all or a comma-separated list of step keys "
            "to require products."
        )

    config = get_realdata_config()
    if config.output_dir is None:
        pytest.skip("Set GRID_CALIBRATION_REALDATA_OUTDIR to require existing real-data products.")
    if not config.output_dir.exists():
        pytest.skip(f"Configured output directory does not exist: {config.output_dir}")

    session = CalibrationSession.from_inputs(
        raw_files=config.raw_files,
        output_dir=config.output_dir,
    )
    rows = product_status_rows(
        session=session,
        product_io_by_step=PRODUCT_IO_BY_STEP,
    )
    summary = format_product_status(rows)

    known_steps = {row["step"] for row in rows}
    if required_steps == {"all"}:
        required_steps = known_steps

    unknown_steps = required_steps - known_steps
    assert not unknown_steps, f"Unknown product step(s): {sorted(unknown_steps)}\n{summary}"

    missing = []
    for row in rows:
        if row["step"] not in required_steps:
            continue
        if not row["loadable"]:
            missing.append(row["step"])
            continue
        if row["kind"] == "per_input" and row["count"] != row["expected"]:
            missing.append(row["step"])

    assert not missing, f"Required real-data products are missing or incomplete: {missing}\n{summary}"


@pytest.mark.slow
def test_realdata_batch_pipeline_can_run_when_explicitly_enabled(tmp_path: Path) -> None:
    config = get_realdata_config()
    if not config.run_pipeline:
        pytest.skip("Set GRID_CALIBRATION_RUN_REAL_PIPELINE=1 to run slow real-data processing.")

    pytest.importorskip("dash")

    output_dir = tmp_path / "grid_calibration_output"
    output_dir.mkdir(parents=True, exist_ok=True)
    session = CalibrationSession.from_inputs(
        raw_files=config.raw_files,
        output_dir=output_dir,
    )

    from grid_calibration.gui.server import app

    app.server.config["session"] = session

    completed_steps: list[str] = []

    for spec in ORDERED_STEP_SPECS:
        if spec.key == "raw-image" or spec.mode != "batch" or spec.pipeline_func is None:
            continue

        try:
            result = spec.pipeline_func(session.raw_files)
        except ModuleNotFoundError as exc:
            pytest.skip(f"Real-data pipeline dependency is not installed: {exc.name}")

        session.set(spec.key, result)
        session.refresh_products()
        completed_steps.append(spec.key)

    assert completed_steps
    for step_key in completed_steps:
        assert session.get(step_key)

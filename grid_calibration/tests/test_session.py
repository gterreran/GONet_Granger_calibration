from __future__ import annotations

from pathlib import Path

import pytest

from grid_calibration.errors import PipelineStepError
from grid_calibration.gui.session import CalibrationSession
from grid_calibration.gui.workflow.product_io import ProductIO, ProductKind


def test_first_raw_file_returns_first_path(tmp_path: Path) -> None:
    session = CalibrationSession(
        raw_files=[tmp_path / "first.jpg", tmp_path / "second.jpg"],
        output_dir=tmp_path / "products",
    )

    assert session.first_raw_file == tmp_path / "first.jpg"


def test_first_raw_file_rejects_empty_session(tmp_path: Path) -> None:
    session = CalibrationSession(raw_files=[], output_dir=tmp_path / "products")

    with pytest.raises(PipelineStepError, match="no raw files"):
        _ = session.first_raw_file


def test_get_and_set_products(tmp_path: Path) -> None:
    session = CalibrationSession(raw_files=[tmp_path / "img.jpg"], output_dir=tmp_path)
    product_path = tmp_path / "product.npz"

    session.set("grid-points", [product_path])

    assert session.get("grid-points") == [product_path]
    assert session.get("missing-step") is None


def test_refresh_products_rediscovers_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_file = tmp_path / "img_001_raw.jpg"
    output_dir = tmp_path / "products"
    product = ProductIO(
        step_key="grid-points",
        suffix="_grid_points.npz",
        kind=ProductKind.PER_INPUT,
    )
    product_path = output_dir / product.relative_path(raw_file)
    product_path.parent.mkdir(parents=True)
    product_path.touch()

    import grid_calibration.gui.session as session_module

    monkeypatch.setattr(session_module, "PRODUCT_IO_BY_STEP", {"grid-points": product})
    session = CalibrationSession(raw_files=[raw_file], output_dir=output_dir)

    session.refresh_products()

    assert session.products["grid-points"] == [product_path]

from __future__ import annotations

from pathlib import Path

import pytest

from grid_calibration.gui.workflow.product_io import ProductKind, discover_products
from grid_calibration.gui.workflow.registry import PRODUCT_IO_BY_STEP

from .synthetic_products import SyntheticSession, write_product


def _raw_files(tmp_path: Path, n: int = 2) -> list[Path]:
    files = [tmp_path / f"site_camera_date_{idx:03d}.jpg" for idx in range(n)]
    for path in files:
        path.write_bytes(b"synthetic")
    return files


def test_synthetic_products_are_discovered_from_output_directory(tmp_path: Path) -> None:
    raw_files = _raw_files(tmp_path, n=2)
    output_dir = tmp_path / "products"

    for product in PRODUCT_IO_BY_STEP.values():
        if product is None:
            continue

        if product.kind is ProductKind.PER_INPUT:
            for raw_file in raw_files:
                write_product(product, output_dir / product.relative_path(raw_file))
        else:
            write_product(product, output_dir / product.relative_path(raw_files[0]))

    discovered = discover_products(PRODUCT_IO_BY_STEP, raw_files, output_dir)

    for step_key, product in PRODUCT_IO_BY_STEP.items():
        if product is None:
            continue

        if product.kind is ProductKind.PER_INPUT:
            assert len(discovered[step_key]) == len(raw_files)
            assert all(path.exists() for path in discovered[step_key])
        else:
            assert discovered[step_key] is not None
            assert discovered[step_key].exists()


def test_discovery_represents_missing_products_without_crashing(tmp_path: Path) -> None:
    raw_files = _raw_files(tmp_path, n=2)
    output_dir = tmp_path / "products"

    full_array = PRODUCT_IO_BY_STEP["full-array"]
    write_product(full_array, output_dir / full_array.relative_path(raw_files[0]))

    discovered = discover_products(PRODUCT_IO_BY_STEP, raw_files, output_dir)

    assert discovered["full-array"] == [output_dir / full_array.relative_path(raw_files[0])]
    assert discovered["grid-points"] == []
    assert discovered["averaged-grid"] is None


@pytest.fixture
def synthetic_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SyntheticSession:
    dash = pytest.importorskip("dash")
    del dash

    raw_files = _raw_files(tmp_path, n=1)
    output_dir = tmp_path / "products"
    products = {"raw-image": raw_files}

    for step_key, product in PRODUCT_IO_BY_STEP.items():
        if product is None:
            continue

        if product.kind is ProductKind.PER_INPUT:
            path = write_product(product, output_dir / product.relative_path(raw_files[0]))
            products[step_key] = [path]
        else:
            path = write_product(product, output_dir / product.relative_path(raw_files[0]))
            products[step_key] = path

    session = SyntheticSession(raw_files=raw_files, output_dir=output_dir, products=products)

    import grid_calibration.gui.session as session_module

    monkeypatch.setattr(session_module, "get_session", lambda: session)
    return session


def test_core_viewers_render_synthetic_products(synthetic_session: SyntheticSession) -> None:
    from dash.development.base_component import Component

    from grid_calibration.gui.steps.full_array.plotting import plot_full_array_product
    from grid_calibration.gui.steps.grid_points.plotting import plot_grid_array
    from grid_calibration.gui.steps.unwrapped_grid.plotting import plot_unwrapped_grid
    from grid_calibration.gui.steps.nominal_grid.plotting import plot_nominal_grid
    from grid_calibration.gui.steps.bootstrapping_grid.plotting import plot_bootstrapping_grid

    rendered = [
        plot_full_array_product(0),
        plot_grid_array(0),
        plot_grid_array(0, average=True),
        plot_unwrapped_grid(None),
        plot_nominal_grid(None),
        plot_bootstrapping_grid(None),
    ]

    assert all(isinstance(component, Component) for component in rendered)


def test_viewers_return_graceful_placeholders_for_missing_or_invalid_selection(
    synthetic_session: SyntheticSession,
) -> None:
    from dash import html

    from grid_calibration.gui.steps.full_array.plotting import plot_full_array_product
    from grid_calibration.gui.steps.grid_points.plotting import plot_grid_array

    synthetic_session.products["full-array"] = []
    assert isinstance(plot_full_array_product(0), html.Div)
    assert isinstance(plot_grid_array(0), html.Div)

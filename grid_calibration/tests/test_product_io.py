from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from grid_calibration.errors import (
    MissingProductError,
    PipelineStepError,
    ProductLoadError,
    ProductSaveError,
)
from grid_calibration.gui.workflow.product_io import (
    ProductIO,
    ProductKind,
    discover_products,
)


@dataclass
class DummySession:
    raw_files: list[Path]
    output_dir: Path
    products: dict[str, Any] = field(default_factory=dict)

    @property
    def first_raw_file(self) -> Path:
        if not self.raw_files:
            raise PipelineStepError("DummySession has no raw files.")
        return self.raw_files[0]

    def get(self, step: str) -> Any:
        return self.products.get(step)

    def set(self, step: str, value: Any) -> None:
        self.products[step] = value


@pytest.fixture
def dummy_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DummySession:
    session = DummySession(
        raw_files=[tmp_path / "img_001_raw.jpg", tmp_path / "img_002_raw.jpg"],
        output_dir=tmp_path / "products",
    )

    import grid_calibration.gui.session as session_module

    monkeypatch.setattr(session_module, "get_session", lambda: session)
    return session


@pytest.fixture
def singleton_product() -> ProductIO:
    return ProductIO(
        step_key="averaged-grid",
        suffix="_averaged_grid.npz",
        kind=ProductKind.SINGLETON,
        required_keys=("grid",),
    )


@pytest.fixture
def per_input_product() -> ProductIO:
    return ProductIO(
        step_key="grid-points",
        suffix="_grid_points.npz",
        kind=ProductKind.PER_INPUT,
        required_keys=("grid",),
        optional_keys=("metadata",),
    )


def test_relative_path_uses_input_stem_for_per_input_product(per_input_product: ProductIO) -> None:
    path = per_input_product.relative_path(Path("/data/image_001.jpg"))

    assert path == Path("image_001_grid_points.npz")


def test_relative_path_uses_first_three_stem_parts_for_singleton_product(
    singleton_product: ProductIO,
) -> None:
    path = singleton_product.relative_path(Path("/data/site_camera_date_extra.jpg"))

    assert path == Path("site_camera_date_averaged_grid.npz")


def test_singleton_expected_path_may_use_session_first_raw_file(
    singleton_product: ProductIO,
    dummy_session: DummySession,
) -> None:
    path = singleton_product.expected_path()

    assert path == dummy_session.output_dir / "img_001_raw_averaged_grid.npz"


def test_per_input_expected_path_requires_input_file(
    per_input_product: ProductIO,
    dummy_session: DummySession,
) -> None:
    with pytest.raises(MissingProductError, match="per-input"):
        per_input_product.expected_path()


def test_per_input_save_requires_input_file_or_explicit_path(
    per_input_product: ProductIO,
    dummy_session: DummySession,
) -> None:
    with pytest.raises(MissingProductError, match="input_file or path"):
        per_input_product.save(grid=np.zeros((2, 2)))


def test_save_load_and_cache_round_trip_for_simple_product(
    per_input_product: ProductIO,
    dummy_session: DummySession,
) -> None:
    input_file = dummy_session.raw_files[0]
    grid = np.arange(6).reshape(3, 2)

    path = per_input_product.save(input_file=input_file, grid=grid)
    loaded_first = per_input_product.load(path)
    loaded_second = per_input_product.load(path)

    assert path == dummy_session.output_dir / "img_001_raw_grid_points.npz"
    np.testing.assert_array_equal(loaded_first["grid"], grid)
    assert loaded_first is loaded_second


def test_save_rejects_missing_required_keys(
    per_input_product: ProductIO,
    dummy_session: DummySession,
) -> None:
    with pytest.raises(ProductSaveError, match="missing required keys"):
        per_input_product.save(input_file=dummy_session.raw_files[0], metadata=np.array([1]))


def test_save_rejects_unexpected_keys(
    per_input_product: ProductIO,
    dummy_session: DummySession,
) -> None:
    with pytest.raises(ProductSaveError, match="unexpected keys"):
        per_input_product.save(
            input_file=dummy_session.raw_files[0],
            grid=np.zeros((1, 2)),
            unexpected=np.array([1]),
        )


def test_load_rejects_npz_missing_required_keys(
    per_input_product: ProductIO,
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad_product.npz"
    np.savez_compressed(path, metadata=np.array([1]))

    with pytest.raises(ProductLoadError, match="missing required NPZ keys"):
        per_input_product.load(path)


def test_encode_decode_round_trip(dummy_session: DummySession) -> None:
    def encode_product(*, data: list[dict[str, int]], params: dict[str, int]) -> dict[str, Any]:
        return {
            "data": np.array(data, dtype=object),
            "params": np.array(params, dtype=object),
        }

    def decode_product(loaded: dict[str, Any]) -> dict[str, Any]:
        return {
            "data": loaded["data"].tolist(),
            "params": loaded["params"].item(),
        }

    product = ProductIO(
        step_key="nominal-grid",
        suffix="_nominal_grid.npz",
        kind=ProductKind.SINGLETON,
        required_keys=("data",),
        optional_keys=("params",),
        allow_pickle=True,
        encode=encode_product,
        decode=decode_product,
    )

    expected_data = [{"idx": 1}, {"idx": 2}]
    expected_params = {"threshold": 3}

    path = product.save(data=expected_data, params=expected_params)
    loaded = product.load(path)

    assert loaded == {"data": expected_data, "params": expected_params}


def test_register_singleton_sets_path_on_session(
    singleton_product: ProductIO,
    dummy_session: DummySession,
) -> None:
    path = singleton_product.register()

    assert path == dummy_session.output_dir / "img_001_raw_averaged_grid.npz"
    assert dummy_session.products["averaged-grid"] == path


def test_register_per_input_requires_explicit_list(
    per_input_product: ProductIO,
    dummy_session: DummySession,
) -> None:
    with pytest.raises(MissingProductError, match="provide a list of paths"):
        per_input_product.register()


def test_register_per_input_rejects_single_path(
    per_input_product: ProductIO,
    dummy_session: DummySession,
) -> None:
    with pytest.raises(TypeError, match="expected list"):
        per_input_product.register(dummy_session.output_dir / "one.npz")


def test_load_index_loads_registered_per_input_product(
    per_input_product: ProductIO,
    dummy_session: DummySession,
) -> None:
    path0 = per_input_product.save(
        input_file=dummy_session.raw_files[0],
        grid=np.array([[1, 2]]),
    )
    path1 = per_input_product.save(
        input_file=dummy_session.raw_files[1],
        grid=np.array([[3, 4]]),
    )
    per_input_product.register([path0, path1])

    loaded = per_input_product.load_index(1)

    np.testing.assert_array_equal(loaded["grid"], np.array([[3, 4]]))


def test_load_index_rejects_out_of_range_index(
    per_input_product: ProductIO,
    dummy_session: DummySession,
) -> None:
    per_input_product.register([dummy_session.output_dir / "one.npz"])

    with pytest.raises(MissingProductError, match="out of range"):
        per_input_product.load_index(1)


def test_discover_products_requires_complete_per_input_products(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    input_files = [tmp_path / "img_001_raw.jpg", tmp_path / "img_002_raw.jpg"]
    output_dir = tmp_path / "products"
    singleton = ProductIO(
        step_key="averaged-grid",
        suffix="_averaged_grid.npz",
        kind=ProductKind.SINGLETON,
        required_keys=("grid",),
    )
    per_input = ProductIO(
        step_key="grid-points",
        suffix="_grid_points.npz",
        kind=ProductKind.PER_INPUT,
        required_keys=("grid",),
    )

    singleton_path = output_dir / singleton.relative_path(input_files[0])
    per_input_path = output_dir / per_input.relative_path(input_files[1])
    singleton_path.parent.mkdir(parents=True)
    singleton_path.touch()
    per_input_path.touch()

    discovered = discover_products(
        {
            "raw-image": None,
            "averaged-grid": singleton,
            "grid-points": per_input,
        },
        input_files,
        output_dir,
    )

    assert discovered == {
        "averaged-grid": singleton_path,
        "grid-points": [],
    }
    assert "Ignoring incomplete per-input product set" in caplog.text


def test_discover_products_returns_complete_per_input_products(tmp_path: Path) -> None:
    input_files = [tmp_path / "img_001_raw.jpg", tmp_path / "img_002_raw.jpg"]
    output_dir = tmp_path / "products"
    per_input = ProductIO(
        step_key="grid-points",
        suffix="_grid_points.npz",
        kind=ProductKind.PER_INPUT,
        required_keys=("grid",),
    )

    expected = []
    for input_file in input_files:
        path = output_dir / per_input.relative_path(input_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        expected.append(path)

    discovered = discover_products(
        {"grid-points": per_input},
        input_files,
        output_dir,
    )

    assert discovered == {"grid-points": expected}


def test_discover_products_can_ignore_downstream_stale_products(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    input_files = [tmp_path / "img_001_raw.jpg", tmp_path / "img_002_raw.jpg"]
    output_dir = tmp_path / "products"
    upstream = ProductIO(
        step_key="grid-points",
        suffix="_grid_points.npz",
        kind=ProductKind.PER_INPUT,
        required_keys=("grid",),
    )
    downstream = ProductIO(
        step_key="averaged-grid",
        suffix="_averaged_grid.npz",
        kind=ProductKind.SINGLETON,
        required_keys=("grid",),
    )

    stale_path = output_dir / downstream.relative_path(input_files[0])
    stale_path.parent.mkdir(parents=True)
    stale_path.touch()

    discovered = discover_products(
        {"grid-points": upstream, "averaged-grid": downstream},
        input_files,
        output_dir,
        ordered_steps=["grid-points", "averaged-grid"],
        stop_at_first_missing=True,
        warn_stale=True,
    )

    assert discovered == {"grid-points": []}
    assert "Ignoring stale product" in caplog.text


def test_discover_products_requires_at_least_one_input(tmp_path: Path) -> None:
    product = ProductIO(
        step_key="grid-points",
        suffix="_grid_points.npz",
        kind=ProductKind.PER_INPUT,
    )

    with pytest.raises(PipelineStepError, match="at least one input"):
        discover_products({"grid-points": product}, [], tmp_path)

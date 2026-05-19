from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pytest

from grid_calibration.errors import MissingProductError
from grid_calibration.gui.steps import STEP_MODULES
from grid_calibration.gui.workflow.product_io import ProductIO, ProductKind
from grid_calibration.gui.workflow.registry import (
    ORDERED_STEPS,
    PRODUCT_IO_BY_STEP,
    RUNNABLE_STEPS,
    STEP_BY_ID,
    import_step_callback_modules,
)


OPTIONAL_EXTERNAL_DEPENDENCIES = {
    "dash",
    "plotly",
    "GONet_Wizard",
}


@dataclass
class DummySession:
    raw_files: list[Path]
    output_dir: Path
    products: dict[str, Any] = field(default_factory=dict)

    @property
    def first_raw_file(self) -> Path:
        return self.raw_files[0]

    def get(self, step: str) -> Any:
        return self.products.get(step)

    def set(self, step: str, value: Any) -> None:
        self.products[step] = value


@pytest.fixture
def dummy_session(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DummySession:
    session = DummySession(
        raw_files=[tmp_path / "site_camera_date_001.jpg"],
        output_dir=tmp_path / "products",
    )

    import grid_calibration.gui.session as session_module

    monkeypatch.setattr(session_module, "get_session", lambda: session)
    return session


def _is_optional_missing_dependency(exc: ModuleNotFoundError) -> bool:
    """
    Return True for missing optional third-party dependencies.

    Internal project import failures should still fail the test, because those are
    exactly the regressions these smoke tests are meant to catch.
    """
    missing_name = exc.name or ""
    return any(
        missing_name == dependency or missing_name.startswith(f"{dependency}.")
        for dependency in OPTIONAL_EXTERNAL_DEPENDENCIES
    )


def _resolve_factory(factory: Callable[[], Callable[..., Any]]) -> Callable[..., Any] | None:
    try:
        return factory()
    except ModuleNotFoundError as exc:
        if _is_optional_missing_dependency(exc):
            return None
        raise


def _minimal_arrays_for_product(product: ProductIO) -> dict[str, Any]:
    """
    Build the smallest schema-valid payload for a registered step product.
    """
    step_key = product.step_key

    if step_key == "full-array":
        arrays: dict[str, Any] = {}
        for key in product.required_keys:
            if key == "image":
                arrays[key] = np.zeros((2, 2), dtype=float)
            elif "bins" in key:
                arrays[key] = np.array([0.0, 1.0], dtype=float)
            else:
                arrays[key] = np.array([1.0], dtype=float)
        return arrays

    if step_key in {"grid-points"}:
        return {"grid": np.zeros((3, 2), dtype=float)}

    if step_key == "averaged-grid":
        return {
            "grid": np.zeros((3, 2), dtype=float),
            "counts": np.ones(3, dtype=int),
        }

    if step_key == "unwrapped-grid":
        return {
            "idx": np.array([0, 1], dtype=int),
            "theta": np.array([0.0, 2.5], dtype=float),
            "r": np.array([10.0, 20.0], dtype=float),
            "pts": np.zeros((2, 2), dtype=float),
            "center": np.array([100.0, 100.0], dtype=float),
        }

    if step_key in {"nominal-grid", "bootstrapping-grid"}:
        data_key = product.required_keys[0]
        return {
            data_key: [
                {
                    "idx": 0,
                    "pixel_x": 10.0,
                    "pixel_y": 20.0,
                    "nominal_r": 2.5,
                    "nominal_theta": 0.0,
                }
            ],
            "params": {"smoke_test": True},
        }

    if step_key == "modeling-results":
        data_key = product.required_keys[0]
        return {
            data_key: {"success": True, "rms": 0.0},
            "params": {"smoke_test": True},
        }

    raise AssertionError(f"No minimal fake product payload defined for {step_key!r}.")


def test_step_modules_expose_declared_step_objects() -> None:
    for module in STEP_MODULES:
        assert hasattr(module, "pipeline_step"), module.__name__
        assert hasattr(module, "product_io"), module.__name__


def test_registered_steps_have_contiguous_order() -> None:
    orders = [STEP_BY_ID[key].order for key in ORDERED_STEPS]

    assert orders == list(range(len(orders)))


def test_registered_factories_resolve_to_callables_when_dependencies_are_available() -> None:
    for step_key in ORDERED_STEPS:
        step = STEP_BY_ID[step_key]

        for factory_name in (
            "viewer_factory",
            "pipeline_factory",
            "initialize_factory",
        ):
            factory = getattr(step, factory_name)
            if factory is None:
                continue

            resolved = _resolve_factory(factory)
            if resolved is None:
                continue

            assert callable(resolved), f"{step_key}.{factory_name} did not resolve to a callable"


def test_batch_runnable_steps_resolve_pipeline_callables_when_dependencies_are_available() -> None:
    for step_key in RUNNABLE_STEPS:
        step = STEP_BY_ID[step_key]
        if step.mode != "batch":
            continue

        assert step.pipeline_factory is not None
        pipeline_func = _resolve_factory(step.pipeline_factory)

        if pipeline_func is None:
            continue

        assert callable(pipeline_func)


def test_product_io_minimal_payload_round_trip_for_each_product(
    tmp_path: Path,
    dummy_session: DummySession,
) -> None:
    for step_key, product in PRODUCT_IO_BY_STEP.items():
        if product is None:
            continue

        product.clear_cache()
        arrays = _minimal_arrays_for_product(product)
        path = tmp_path / "products" / f"{step_key}.npz"

        saved_path = product.save(path=path, **arrays)
        loaded = product.load(saved_path)

        for key in product.required_keys:
            assert key in loaded, f"{step_key!r} did not load required key {key!r}"


def test_per_input_products_still_require_explicit_paths_for_implicit_load_and_register(
    dummy_session: DummySession,
) -> None:
    for step_key, product in PRODUCT_IO_BY_STEP.items():
        if product is None or product.kind is not ProductKind.PER_INPUT:
            continue

        with pytest.raises(MissingProductError):
            product.load()

        with pytest.raises(MissingProductError):
            product.register()


def test_step_callback_modules_import_when_dash_is_available() -> None:
    try:
        modules = import_step_callback_modules()
    except ModuleNotFoundError as exc:
        if _is_optional_missing_dependency(exc):
            return
        raise

    assert all(module.__name__.endswith(".callbacks") for module in modules)

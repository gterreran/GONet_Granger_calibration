from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

dash = pytest.importorskip("dash")
no_update = dash.no_update

import grid_calibration.gui.callbacks.pipeline as pipeline_callbacks
import grid_calibration.gui.callbacks.viewer as viewer_callbacks


@dataclass
class DummySession:
    raw_files: list[Path]
    output_dir: Path
    products: dict[str, Any] = field(default_factory=dict)

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
    monkeypatch.setattr(pipeline_callbacks, "get_session", lambda: session)
    return session


def test_start_step_ignores_empty_or_unknown_requests() -> None:
    assert pipeline_callbacks.start_step(None) == (no_update, no_update, no_update, no_update)
    assert pipeline_callbacks.start_step({"step": "does-not-exist"}) == (
        no_update,
        no_update,
        no_update,
        no_update,
    )


def test_start_step_runs_batch_step_and_stores_product(
    dummy_session: DummySession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, Any] = {}

    def pipeline_func(raw_files: list[Path]) -> Path:
        calls["raw_files"] = raw_files
        return Path("batch-product.npz")

    spec = SimpleNamespace(
        mode="batch",
        pipeline_func=pipeline_func,
    )
    monkeypatch.setitem(pipeline_callbacks.STEP_BY_ID, "fake-batch", spec)

    status, active_step, result, plotting_area = pipeline_callbacks.start_step(
        {"step": "fake-batch", "request_token": "token-1"}
    )

    assert status == "Step fake-batch completed."
    assert active_step == "fake-batch"
    assert result == {
        "step": "fake-batch",
        "status": "completed",
        "request_token": "token-1",
    }
    assert plotting_area is no_update
    assert dummy_session.get("fake-batch") == Path("batch-product.npz")
    assert calls["raw_files"] == dummy_session.raw_files


def test_start_step_initializes_interactive_step(
    dummy_session: DummySession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = SimpleNamespace(
        mode="interactive",
        initialize_interactive_state=lambda: "interactive controls",
    )
    monkeypatch.setitem(pipeline_callbacks.STEP_BY_ID, "fake-interactive", spec)

    status, active_step, result, plotting_area = pipeline_callbacks.start_step(
        {"step": "fake-interactive", "request_token": "token-2"}
    )

    assert status == "Step fake-interactive started. Waiting for user input."
    assert active_step == "fake-interactive"
    assert result is no_update
    assert plotting_area == "interactive controls"
    assert dummy_session.get("fake-interactive") is None


def test_finalize_step_ignores_empty_or_incomplete_results() -> None:
    empty = pipeline_callbacks._empty_outputs()

    assert pipeline_callbacks.finalize_step(None, []) == empty
    assert pipeline_callbacks.finalize_step({"step": "grid-points", "status": "running"}, []) == empty


def test_finalize_step_rebuilds_options_for_list_product(
    dummy_session: DummySession,
) -> None:
    step = pipeline_callbacks.ORDERED_STEPS[1]
    dummy_session.set(step, [Path("one.npz"), Path("two.npz")])
    options = [[] for _ in pipeline_callbacks.ORDERED_STEPS]

    status, selected_step, disabled_buttons, new_options, disabled_options, disabled_rows = (
        pipeline_callbacks.finalize_step(
            {"step": step, "status": "completed"},
            options,
        )
    )

    assert status == f"Completed step: {step}"
    assert selected_step == step
    assert new_options[1] == [
        {"label": "one.npz", "value": 0},
        {"label": "two.npz", "value": 1},
    ]
    assert len(disabled_buttons) == len(pipeline_callbacks.RUNNABLE_STEPS)
    assert len(disabled_options) == len(pipeline_callbacks.ORDERED_STEPS)
    assert disabled_rows == disabled_options


def test_finalize_step_rebuilds_options_for_singleton_product(
    dummy_session: DummySession,
) -> None:
    step = pipeline_callbacks.ORDERED_STEPS[-1]
    step_index = pipeline_callbacks.ORDERED_STEPS.index(step)
    dummy_session.set(step, Path("singleton.npz"))
    options = [[] for _ in pipeline_callbacks.ORDERED_STEPS]

    result = pipeline_callbacks.finalize_step(
        {"step": step, "status": "completed"},
        options,
    )

    assert result[0] == f"Completed step: {step}"
    assert result[1] == step
    assert result[3][step_index] == [{"label": "singleton.npz", "value": 0}]


def test_finalize_step_handles_missing_product_without_crashing(
    dummy_session: DummySession,
) -> None:
    step = pipeline_callbacks.ORDERED_STEPS[1]
    options = [[] for _ in pipeline_callbacks.ORDERED_STEPS]

    assert pipeline_callbacks.finalize_step(
        {"step": step, "status": "completed"},
        options,
    ) == pipeline_callbacks._empty_outputs()


def test_update_plotting_area_ignores_missing_selection() -> None:
    assert viewer_callbacks.update_plotting_area(None, []) is no_update
    assert viewer_callbacks.update_plotting_area("does-not-exist", []) is no_update


def test_update_plotting_area_calls_registered_viewer(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def viewer(idx: int) -> str:
        calls.append(idx)
        return f"plot-{idx}"

    step = viewer_callbacks.ORDERED_STEPS[1]
    original_spec = viewer_callbacks.STEP_BY_ID[step]
    monkeypatch.setitem(
        viewer_callbacks.STEP_BY_ID,
        step,
        SimpleNamespace(viewer_func=viewer),
    )

    try:
        idx_values = [None for _ in viewer_callbacks.ORDERED_STEPS]
        idx_values[1] = 3

        assert viewer_callbacks.update_plotting_area(step, idx_values) == "plot-3"
        assert calls == [3]
    finally:
        monkeypatch.setitem(viewer_callbacks.STEP_BY_ID, step, original_spec)


def test_update_plotting_area_defaults_missing_index_to_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    step = viewer_callbacks.ORDERED_STEPS[1]
    original_spec = viewer_callbacks.STEP_BY_ID[step]
    monkeypatch.setitem(
        viewer_callbacks.STEP_BY_ID,
        step,
        SimpleNamespace(viewer_func=lambda idx: f"plot-{idx}"),
    )

    try:
        idx_values = [None for _ in viewer_callbacks.ORDERED_STEPS]
        assert viewer_callbacks.update_plotting_area(step, idx_values) == "plot-0"
    finally:
        monkeypatch.setitem(viewer_callbacks.STEP_BY_ID, step, original_spec)

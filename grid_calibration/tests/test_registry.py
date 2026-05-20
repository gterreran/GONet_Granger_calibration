from __future__ import annotations

from grid_calibration.gui.workflow.registry import (
    ORDERED_STEP_SPECS,
    ORDERED_STEPS,
    PRODUCT_IO_BY_STEP,
    RUNNABLE_STEPS,
    STEP_BY_ID,
)


def test_registered_step_keys_are_unique_and_ordered() -> None:
    assert len(ORDERED_STEPS) == len(set(ORDERED_STEPS))
    assert ORDERED_STEPS == [step.key for step in ORDERED_STEP_SPECS]
    assert ORDERED_STEP_SPECS == sorted(ORDERED_STEP_SPECS, key=lambda step: step.order)


def test_every_registered_step_has_matching_product_key_or_no_product() -> None:
    assert set(PRODUCT_IO_BY_STEP) == set(STEP_BY_ID)

    for step_key, product in PRODUCT_IO_BY_STEP.items():
        if product is not None:
            assert product.step_key == step_key


def test_runnable_steps_exclude_only_first_step() -> None:
    assert RUNNABLE_STEPS == ORDERED_STEPS[1:]


def test_batch_runnable_steps_have_pipeline_factories() -> None:
    for step_key in RUNNABLE_STEPS:
        step = STEP_BY_ID[step_key]
        if step.mode == "batch":
            assert step.pipeline_factory is not None


def test_all_non_raw_steps_have_viewer_factories() -> None:
    for step_key in RUNNABLE_STEPS:
        step = STEP_BY_ID[step_key]
        assert step.viewer_factory is not None

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional, Callable
from ..pipeline import (
    build_full_arrays_for_images,
    detect_grid_points_for_images,
    average_detected_grids_images,
)
from .plot_utils import (
    plot_raw_image,
    plot_full_array_product,
    plot_grid_array,
)

StepMode = Literal["batch", "interactive"]
OptionKind = Literal["dropdown", "label"]

@dataclass(frozen=True)
class StepSpec:
    step: str
    label: str
    option_kind: OptionKind           # "dropdown"
    mode: StepMode                    # "batch" | "interactive"
    order: int
    button_label: Optional[str] = None

    pipeline_func: Optional[Callable] = None
    viewer_func: Optional[Callable] = None

    enabled_if: Callable[[dict], bool] = lambda df: True
    clickable_if: Callable[[dict], bool] = lambda df: True

STEPS = [
    StepSpec(
        step="raw-image",
        label="Raw images",
        option_kind="dropdown",
        mode="batch",
        order=0,
        viewer_func=plot_raw_image,
    ),
    StepSpec(
        step="full-array",
        label="Build full arrays",
        option_kind="dropdown",
        mode="batch",
        order=1,
        button_label="1. Build full arrays",
        pipeline_func=build_full_arrays_for_images,
        viewer_func=plot_full_array_product,
        enabled_if=lambda df: bool(df.get("raw-image")),
        clickable_if=lambda df: bool(df.get("full-array")),
        ),
    StepSpec(
        step="grid-points",
        label="Detect grid points",
        option_kind="dropdown",
        mode="batch",
        order=2,
        button_label="2. Detect grid points",
        pipeline_func=detect_grid_points_for_images,
        viewer_func=plot_grid_array,
        enabled_if=lambda df: bool(df.get("full-array")),
        clickable_if=lambda df: bool(df.get("grid-points")),
    ),
    StepSpec(
        step="averaged-grid",
        label="Average grids",
        option_kind="label",
        mode="batch",
        order=3,
        button_label="3. Average grids",
        pipeline_func=average_detected_grids_images,
        viewer_func=plot_grid_array,
        enabled_if=lambda df: bool(df.get("grid-points")),
        clickable_if=lambda df: bool(df.get("averaged-grid")),
    ),
    StepSpec(
        step="calibrated-grid",
        label="Calibrated grid",
        option_kind="label",
        mode="interactive",  # important for later
        order=4,
        button_label="4. Calibrate grid",
        pipeline_func=None,
        viewer_func=None,
        enabled_if=lambda df: bool(df.get("averaged-grid")),
        clickable_if=lambda df: bool(df.get("calibrated-grid")),
    ),
]

STEP_BY_ID = {s.step: s for s in STEPS}
ORDERED_STEPS = [s.step for s in sorted(STEPS, key=lambda s: s.order)]
RUNNABLE_STEPS = ORDERED_STEPS[1:]

PIPELINE_FUNCS = {s.step: s.pipeline_func for s in STEPS if s.pipeline_func}
VIEWER_FUNCS   = {s.step: s.viewer_func   for s in STEPS if s.viewer_func}
ENABLE_RULES   = {s.step: s.enabled_if    for s in STEPS}
CLICKABLE_RULES= {s.step: s.clickable_if  for s in STEPS}
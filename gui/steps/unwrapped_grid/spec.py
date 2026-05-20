# grid_calibration/gui/steps/unwrapped_grid/spec.py
from __future__ import annotations

"""Workflow specification and singleton-product descriptor for the unwrapped-grid step."""

from ...workflow import PipelineStepSpec, ProductKind, ProductIO
from .keys import STEP_KEY, REQUIRED_ARRAY_KEYS, IDX_KEY, THETA_KEY, R_KEY, POINTS_KEY, CENTER_KEY
from ...workflow.io_helpers import maybe_item

def decode_product(loaded):
    return {
        IDX_KEY: loaded[IDX_KEY],
        THETA_KEY: loaded[THETA_KEY],
        R_KEY: loaded[R_KEY],
        POINTS_KEY: loaded[POINTS_KEY],
        CENTER_KEY: maybe_item(loaded[CENTER_KEY]),
    }

product_io = ProductIO(
    step_key=STEP_KEY,
    suffix="_unwrapped_grid.npz",
    kind=ProductKind.SINGLETON,
    required_keys=REQUIRED_ARRAY_KEYS,
    allow_pickle=True,
    decode=decode_product,
)

def viewer_factory():
    from .plotting import plot_unwrapped_grid
    return plot_unwrapped_grid

def initialize_factory():
    from .plotting import initialize_unwrapped_grid
    return initialize_unwrapped_grid

pipeline_step = PipelineStepSpec.from_dict({
    "key": STEP_KEY,
    "label": "Unwrap grids",
    "order": 4,
    "mode": "interactive",
    "product_kind": product_io.kind,
})
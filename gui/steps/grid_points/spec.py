# grid_calibration/gui/steps/grid_points/spec.py

from __future__ import annotations
from ...workflow import PipelineStepSpec, ProductKind, ProductIO
from .keys import STEP_KEY, REQUIRED_ARRAY_KEYS

product_io = ProductIO(
    step_key=STEP_KEY,
    suffix="_grid_points.npz",
    kind=ProductKind.PER_INPUT,
    required_keys=REQUIRED_ARRAY_KEYS,
    allow_pickle=False,
)

def viewer_factory():
    from .plotting import plot_grid_array
    return plot_grid_array

def pipeline_factory():
    from .processing import detect_grid_points_for_images
    return detect_grid_points_for_images

pipeline_step = PipelineStepSpec.from_dict({
    "key": STEP_KEY,
    "label": "Detect grid points",
    "order": 2,
    "mode": "batch",
    "product_kind": product_io.kind,
})
# grid_calibration/gui/steps/averaged_grid/spec.py

from __future__ import annotations
from ...workflow import PipelineStepSpec, ProductKind, ProductIO
from .keys import STEP_KEY, REQUIRED_ARRAY_KEYS

product_io = ProductIO(
    step_key=STEP_KEY,
    suffix="_averaged_grid.npz",
    kind=ProductKind.SINGLETON,
    required_keys=REQUIRED_ARRAY_KEYS,
    allow_pickle=False,
)

def viewer_factory():
    from ..grid_points.plotting import plot_grid_array
    return plot_grid_array

def pipeline_factory():
    from .processing import average_detected_grids_images
    return average_detected_grids_images

pipeline_step = PipelineStepSpec.from_dict({
    "key": STEP_KEY,
    "label": "Average grids",
    "order": 3,
    "mode": "batch",
    "product_kind": product_io.kind,
})
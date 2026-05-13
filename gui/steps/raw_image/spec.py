# grid_calibration/gui/steps/raw_image/spec.py

from __future__ import annotations
from ...workflow import PipelineStepSpec
from .keys import STEP_KEY

def viewer_factory():
    from .plotting import plot_raw_image
    return plot_raw_image

product_io = None  # No products are produced by this step

pipeline_step = PipelineStepSpec.from_dict({
    "key": STEP_KEY,
    "label": "Raw images",
    "order": 0,
    "mode": "batch",
    "product": None,
})
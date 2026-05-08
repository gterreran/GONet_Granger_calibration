# grid_calibration/gui/steps/raw_image/spec.py

from __future__ import annotations
from ...workflow.specs import PipelineStepSpec, ProductKind
from .plotting import plot_raw_image

pipeline_step = PipelineStepSpec.from_dict({
    "key": "raw-image",
    "label": "Raw images",
    "order": 0,
    "mode": "batch",
    "product": None,
    "viewer_func" : plot_raw_image,
})
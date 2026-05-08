# grid_calibration/gui/steps/full_array/spec.py

from __future__ import annotations
from ...workflow.specs import PipelineStepSpec, ProductKind
from .plotting import plot_full_array_product
from .processing import build_full_arrays_for_images
    
pipeline_step = PipelineStepSpec.from_dict({
    "key": "full-array",
    "label": "Build full arrays",
    "order": 1,
    "mode": "batch",
    "product": {
        "suffix": "_full_array.npz",
        "kind": ProductKind.PER_INPUT,
    },
    "viewer_func": plot_full_array_product,
    "pipeline_func":build_full_arrays_for_images
})
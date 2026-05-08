from __future__ import annotations
from ...workflow.specs import PipelineStepSpec, ProductKind
from .plotting import plot_grid_array
from .processing import detect_grid_points_for_images

pipeline_step = PipelineStepSpec.from_dict({
    "key": "grid-points",
    "label": "Detect grid points",
    "order": 2,
    "mode": "batch",
    "product": {
        "suffix": "_grid_points.npz",
        "kind": ProductKind.PER_INPUT,
    },
    "viewer_func": plot_grid_array,
    "pipeline_func":detect_grid_points_for_images,
})

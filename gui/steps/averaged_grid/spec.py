from __future__ import annotations
from ...workflow.specs import PipelineStepSpec, ProductKind
from ..grid_points.plotting import plot_grid_array
from .processing import average_detected_grids_images
    
pipeline_step = PipelineStepSpec.from_dict({
    "key": "averaged-grid",
    "label": "Average grids",
    "order": 3,
    "mode": "batch",
    "product": {
        "suffix": "_averaged_grid.npz",
        "kind": ProductKind.SINGLETON,
    },
    "viewer_func": plot_grid_array,
    "pipeline_func": average_detected_grids_images,
})
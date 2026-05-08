from __future__ import annotations
from ...workflow.specs import PipelineStepSpec, ProductKind
from .plotting import plot_unwrapped_grid, initialize_unwrapped_grid

pipeline_step = PipelineStepSpec.from_dict({
    "key": "unwrapped-grid",
    "label": "Unwrap grids",
    "order": 4,
    "mode": "interactive",
    "product": {
        "suffix": "_unwrapped_grid.npz",
        "kind": ProductKind.SINGLETON,
    },
    "viewer_func": plot_unwrapped_grid,
    "initialize_interactive_state": initialize_unwrapped_grid,
})
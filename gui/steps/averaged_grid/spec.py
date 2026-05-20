# grid_calibration/gui/steps/averaged_grid/spec.py
"""
Workflow specification and product descriptor for the averaged-grid step.

The averaged-grid step is a batch singleton-product step. It consumes the
per-input ``*_grid_points.npz`` products and produces one shared
``*_averaged_grid.npz`` product for the workflow session.
"""

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
"""
Singleton product descriptor for averaged-grid products.
"""

def viewer_factory():
    """
    Return the averaged-grid viewer callable.

    Returns
    -------
    callable
        The
        :func:`~grid_calibration.gui.steps.grid_points.plotting.plot_grid_array`
        function configured to visualize the averaged-grid overlay.
    """
    from ..grid_points.plotting import plot_grid_array
    return plot_grid_array

def pipeline_factory():
    """
    Return the averaged-grid batch-processing callable.

    Returns
    -------
    callable
        The
        :func:`~grid_calibration.gui.steps.averaged_grid.processing.average_detected_grids_images`
        function.
    """
    from .processing import average_detected_grids_images
    return average_detected_grids_images

pipeline_step = PipelineStepSpec.from_dict({
    "key": STEP_KEY,
    "label": "Average grids",
    "order": 3,
    "mode": "batch",
    "product_kind": product_io.kind,
})
"""
Workflow specification for the averaged-grid step.
"""

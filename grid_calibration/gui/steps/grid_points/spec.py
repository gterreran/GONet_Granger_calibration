# grid_calibration/gui/steps/grid_points/spec.py
"""
Workflow specification and product descriptor for the grid-points step.

The grid-points step is a batch, per-input product step. It consumes the
``*_full_array.npz`` products from the previous workflow stage and produces one
``*_grid_points.npz`` product per input image.
"""

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
"""
Product IO descriptor for grid-point products.
"""

def viewer_factory():
    """
    Return the grid-points viewer callable.

    Returns
    -------
    callable
        The :func:`~grid_calibration.gui.steps.grid_points.plotting.plot_grid_array`
        function.
    """
    from .plotting import plot_grid_array
    return plot_grid_array

def pipeline_factory():
    """
    Return the grid-points batch-processing callable.

    Returns
    -------
    callable
        The
        :func:`~grid_calibration.gui.steps.grid_points.processing.detect_grid_points_for_images`
        function.
    """
    from .processing import detect_grid_points_for_images
    return detect_grid_points_for_images

pipeline_step = PipelineStepSpec.from_dict({
    "key": STEP_KEY,
    "label": "Detect grid points",
    "order": 2,
    "mode": "batch",
    "product_kind": product_io.kind,
})
"""
Workflow specification for the grid-points step.
"""

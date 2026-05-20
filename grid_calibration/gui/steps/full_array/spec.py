# grid_calibration/gui/steps/full_array/spec.py
"""
Workflow specification and product descriptor for the full-array step.

The full-array step is a batch, per-input product step. It consumes raw input
images from the session and produces one ``*_full_array.npz`` file per input
image.
"""

from __future__ import annotations
from ...workflow import PipelineStepSpec, ProductKind, ProductIO
from .keys import STEP_KEY, REQUIRED_ARRAY_KEYS

product_io = ProductIO(
    step_key=STEP_KEY,
    suffix="_full_array.npz",
    kind=ProductKind.PER_INPUT,
    required_keys=REQUIRED_ARRAY_KEYS,
    allow_pickle=False,
)
"""
Product IO descriptor for full-array products.

The descriptor defines the product suffix, per-input behavior, NPZ schema, and
pickle policy used by the workflow.
"""

def viewer_factory():
    """
    Return the full-array viewer callable.

    Returns
    -------
    callable
        The :func:`~grid_calibration.gui.steps.full_array.plotting.plot_full_array_product`
        function.

    Notes
    -----
    The local import keeps registry construction lightweight and avoids
    importing Plotly/Dash plotting modules until the viewer is actually needed.
    """
    from .plotting import plot_full_array_product
    return plot_full_array_product

def pipeline_factory():
    """
    Return the full-array batch-processing callable.

    Returns
    -------
    callable
        The :func:`~grid_calibration.gui.steps.full_array.processing.build_full_arrays_for_images`
        function.
    """
    from .processing import build_full_arrays_for_images
    return build_full_arrays_for_images

pipeline_step = PipelineStepSpec.from_dict({
    "key": STEP_KEY,
    "label": "Build full arrays",
    "order": 1,
    "mode": "batch",
    "product_kind": product_io.kind,
})
"""
Workflow specification for the full-array step.

The specification is created with
:meth:`~grid_calibration.gui.workflow.specs.PipelineStepSpec.from_dict`, which
discovers ``viewer_factory`` and ``pipeline_factory`` from this module's global
namespace.
"""

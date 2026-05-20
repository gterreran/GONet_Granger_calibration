# grid_calibration/gui/steps/raw_image/spec.py
"""
Workflow specification for the raw-image step.

This module defines the registry-facing objects required by
:mod:`grid_calibration.gui.workflow.registry`. The raw-image step is a
viewer/source step: it displays input files already attached to the
:class:`~grid_calibration.gui.session.CalibrationSession` and does not produce a
derived product.
"""

from __future__ import annotations
from ...workflow import PipelineStepSpec
from .keys import STEP_KEY

def viewer_factory():
    """
    Return the raw-image viewer callable.

    The factory performs a local import so the workflow registry can import step
    specifications without immediately importing Plotly, Dash plotting helpers,
    or :mod:`GONet_Wizard` raw-file readers.

    Returns
    -------
    callable
        The :func:`~grid_calibration.gui.steps.raw_image.plotting.plot_raw_image`
        viewer function.
    """
    from .plotting import plot_raw_image
    return plot_raw_image

product_io = None  # No products are produced by this step
"""
Product IO descriptor for the raw-image step.

This value is always :data:`None` because raw images are external inputs. The
session stores the input paths directly under :data:`STEP_KEY`.
"""

pipeline_step = PipelineStepSpec.from_dict({
    "key": STEP_KEY,
    "label": "Raw images",
    "order": 0,
    "mode": "batch",
    "product": None,
})
"""
Workflow specification for the raw-image step.

The step has order ``0`` and acts as the source of the workflow. Its viewer is
provided through :func:`viewer_factory`; it has no pipeline function and no
:class:`~grid_calibration.gui.workflow.product_io.ProductIO` product.
"""

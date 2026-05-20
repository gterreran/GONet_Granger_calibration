# grid_calibration/gui/steps/raw_image/__init__.py
"""
Raw-image step package.

The raw-image step is the source step for the calibration workflow. Unlike later
steps, it does not produce a serialized
:class:`~grid_calibration.gui.workflow.product_io.ProductIO` product. Instead,
the active :class:`~grid_calibration.gui.session.CalibrationSession` stores the
input image paths directly under the ``"raw-image"`` step key.

This package exposes the two names expected by the workflow registry:

``pipeline_step``
    The :class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec`
    describing the step.

``product_io``
    Always :data:`None` for this step because raw images are external inputs,
    not derived products.
"""

from .spec import product_io, pipeline_step

__all__ = [
    "product_io",
    "pipeline_step",
]

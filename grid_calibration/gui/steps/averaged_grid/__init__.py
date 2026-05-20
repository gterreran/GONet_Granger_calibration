# grid_calibration/gui/steps/averaged_grid/__init__.py
"""
Averaged-grid step package.

This step aggregates the per-input grid-point detections into a single
singleton workflow product. The resulting ``*_averaged_grid.npz`` product
contains the consensus grid intersections shared across multiple images.

Unlike earlier per-input steps, the averaged-grid step uses a singleton
:class:`~grid_calibration.gui.workflow.product_io.ProductIO`: only one averaged
product exists for the full workflow session.

The package exposes the workflow-registry interface expected by
:mod:`grid_calibration.gui.workflow.registry`:

``pipeline_step``
    The :class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec`
    describing the step.

``product_io``
    The singleton
    :class:`~grid_calibration.gui.workflow.product_io.ProductIO`
    descriptor for the averaged-grid product.
"""

from .spec import product_io, pipeline_step

__all__ = [
    "product_io",
    "pipeline_step",
]

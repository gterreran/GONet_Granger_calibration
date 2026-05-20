# grid_calibration/gui/steps/bootstrapping_grid/__init__.py
"""
Bootstrapping-grid step package.

This step expands a smaller set of nominal-grid assignments into a denser set of
calibration records suitable for distortion modeling. It consumes the averaged
grid and nominal-grid products and produces a singleton
``*_bootstrapped_grid.npz`` product.

The package exposes the standard workflow-registry API:

``pipeline_step``
    The :class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec`
    describing the bootstrapping step.

``product_io``
    The :class:`~grid_calibration.gui.workflow.product_io.ProductIO`
    responsible for encoding, decoding, loading, saving, and registering the
    bootstrapped product.
"""


from .spec import product_io, pipeline_step

__all__ = [
    "product_io",
    "pipeline_step",
]

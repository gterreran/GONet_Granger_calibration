# grid_calibration/gui/steps/nominal_grid/__init__.py
"""
Nominal-grid step package.

This step assigns measured unwrapped grid detections to the nominal polar grid.
It consumes the singleton unwrapped-grid product and produces a singleton
``*_nominal_grid.npz`` product containing semantic assignment records and the
parameters used to create them.

The package exposes the standard step-registry API:

``pipeline_step``
    The :class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec`
    describing the interactive nominal-grid step.

``product_io``
    The :class:`~grid_calibration.gui.workflow.product_io.ProductIO`
    responsible for saving, loading, encoding, decoding, and registering the
    nominal-grid product.
"""


from .spec import product_io, pipeline_step

__all__ = [
    "product_io",
    "pipeline_step",
]

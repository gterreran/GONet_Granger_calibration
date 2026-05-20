# grid_calibration/gui/steps/modeling_results/__init__.py
"""
Modeling-results step package.

This step fits the distortion model from bootstrapped nominal-grid assignment
records and stores the fit result as a singleton semantic product. It is the
final processing step in the calibration workflow.

The package exposes the standard workflow-registry API:

``pipeline_step``
    The :class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec`
    describing the modeling-results step.

``product_io``
    The :class:`~grid_calibration.gui.workflow.product_io.ProductIO`
    responsible for encoding, decoding, loading, saving, and registering the
    modeling-results product.
"""


from .spec import product_io, pipeline_step

__all__ = [
    "product_io",
    "pipeline_step",
]

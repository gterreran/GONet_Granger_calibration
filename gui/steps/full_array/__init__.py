# grid_calibration/gui/steps/full_array/__init__.py
"""
Full-array step package.

This step converts each input GONet image into a derived full-array product.
It is the first product-producing step in the calibration workflow and uses a
per-input :class:`~grid_calibration.gui.workflow.product_io.ProductIO`
descriptor: one ``*_full_array.npz`` file is expected for each raw input image.

The package exposes the registry-facing objects required by
:mod:`grid_calibration.gui.workflow.registry`:

``pipeline_step``
    The :class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec`
    describing the step.

``product_io``
    The :class:`~grid_calibration.gui.workflow.product_io.ProductIO`
    responsible for product paths, schema validation, loading, caching, and
    session registration.
"""

from .spec import product_io, pipeline_step

__all__ = [
    "product_io",
    "pipeline_step",
]

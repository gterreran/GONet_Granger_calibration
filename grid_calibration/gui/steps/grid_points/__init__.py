# grid_calibration/gui/steps/grid_points/__init__.py
"""
Grid-points step package.

This step detects candidate calibration-grid intersections from the derived
full-array images. It is a per-input product step: each input image produces one
``*_grid_points.npz`` file containing the detected grid-point coordinates.

The package exposes the workflow registry interface expected by
:mod:`grid_calibration.gui.workflow.registry`:

``pipeline_step``
    The :class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec`
    describing the step.

``product_io``
    The :class:`~grid_calibration.gui.workflow.product_io.ProductIO`
    responsible for path resolution, schema validation, loading, caching, and
    session registration.
"""

from .spec import product_io, pipeline_step

__all__ = [
    "product_io",
    "pipeline_step",
]

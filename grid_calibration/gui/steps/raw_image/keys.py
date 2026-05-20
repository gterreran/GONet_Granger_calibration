# grid_calibration/gui/steps/raw_image/keys.py
"""
Constants for the raw-image step.

The step key defined here must match the key used in the corresponding
:class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec`. It is also the
key used by :class:`~grid_calibration.gui.session.CalibrationSession.products`
to store the list of input raw-image files.
"""

STEP_KEY = "raw-image"
"""
Workflow key for the raw-image source step.

This step is special because the registered value is a list of input image
paths, not a product path produced by
:class:`~grid_calibration.gui.workflow.product_io.ProductIO`.
"""

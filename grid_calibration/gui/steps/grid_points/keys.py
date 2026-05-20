# grid_calibration/gui/steps/grid_points/keys.py
"""
Product keys and schema constants for the grid-points step.

Grid-point products store the detected intersection coordinates extracted from
full-array images. The schema defined here is enforced by
:class:`~grid_calibration.gui.workflow.product_io.ProductIO`.
"""

STEP_KEY = "grid-points"
"""
Workflow key for the grid-points step.
"""

GRID_KEY = "grid"
"""
NPZ key containing the detected grid-point coordinates.

The stored array is expected to have shape ``(N, 2)`` and contain image-space
``(y, x)`` coordinates.
"""

REQUIRED_ARRAY_KEYS = (GRID_KEY,)
"""
Required NPZ keys for valid grid-points products.
"""

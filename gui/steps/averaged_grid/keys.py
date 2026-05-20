# grid_calibration/gui/steps/averaged_grid/keys.py
"""
Product keys and schema constants for the averaged-grid step.

The averaged-grid product stores the consensus grid intersections derived from
multiple grid-point detections, together with the number of contributing images
for each averaged point.
"""

STEP_KEY = "averaged-grid"
"""
Workflow key for the averaged-grid step.
"""

GRID_KEY = "grid"
"""
NPZ key containing the averaged grid coordinates.

The stored array is expected to have shape ``(N, 2)`` and contain image-space
``(y, x)`` coordinates.
"""

COUNTS_KEY = "counts"
"""
NPZ key containing the number of contributing images per averaged point.
"""

REQUIRED_ARRAY_KEYS = (GRID_KEY, COUNTS_KEY)
"""
Required NPZ keys for valid averaged-grid products.
"""

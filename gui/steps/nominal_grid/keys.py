# grid_calibration/gui/steps/nominal_grid/key.py
"""
Product keys and schema constants for the nominal-grid step.

The nominal-grid product stores semantic Python records, so it uses
``allow_pickle=True`` together with explicit encode/decode hooks in
:mod:`grid_calibration.gui.steps.nominal_grid.spec`.
"""


STEP_KEY = "nominal-grid"

DATA_KEY = "nominal_assignment"
PARAMS_KEY = "params"

REQUIRED_ARRAY_KEYS = (DATA_KEY,)
OPTIONAL_ARRAY_KEYS = (PARAMS_KEY,)

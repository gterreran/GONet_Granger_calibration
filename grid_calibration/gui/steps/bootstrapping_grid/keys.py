# grid_calibration/gui/steps/bootstrapping_grid/key.py
"""
Product keys and schema constants for the bootstrapping-grid step.

The bootstrapped product stores semantic assignment records. It therefore uses
``allow_pickle=True`` and explicit encode/decode hooks in
:mod:`grid_calibration.gui.steps.bootstrapping_grid.spec`.
"""


STEP_KEY = "bootstrapping-grid"

DATA_KEY = "bootstrapped_nominal_assignment"
PARAMS_KEY = "params"

REQUIRED_ARRAY_KEYS = (DATA_KEY,)
OPTIONAL_ARRAY_KEYS = (PARAMS_KEY,)

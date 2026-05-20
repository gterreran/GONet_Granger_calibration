# grid_calibration/gui/steps/modeling_results/key.py
"""
Product keys and schema constants for the modeling-results step.

The modeling-results product stores a semantic
:class:`~grid_calibration.gui.steps.modeling_results.processing.results.FitResult`
object, so it uses ``allow_pickle=True`` and explicit encode/decode hooks in
:mod:`grid_calibration.gui.steps.modeling_results.spec`.
"""


STEP_KEY = "modeling-results"

DATA_KEY = "fit_result"
PARAMS_KEY = "params"

REQUIRED_ARRAY_KEYS = (DATA_KEY,)
OPTIONAL_ARRAY_KEYS = (PARAMS_KEY,)

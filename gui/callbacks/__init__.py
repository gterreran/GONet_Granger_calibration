# grid_calibration/gui/callbacks/__init__.py
from __future__ import annotations

# Import order doesn't matter much, but I like system first so logging is available.
from . import pipeline  # noqa: F401
from . import system    # noqa: F401
from . import viewer    # noqa: F401

from ..workflow.registry import import_step_callback_modules

import_step_callback_modules()
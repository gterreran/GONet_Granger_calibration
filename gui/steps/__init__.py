# grid_calibration/gui/steps/__init__.py

from . import raw_image
from . import full_array
from . import grid_points
from . import averaged_grid
from . import unwrapped_grid
from . import nominal_grid
from . import bootstrapping_grid
from . import modeling_results


STEP_MODULES = [
    raw_image,
    full_array,
    grid_points,
    averaged_grid,
    unwrapped_grid,
    nominal_grid,
    bootstrapping_grid,
    modeling_results,
]
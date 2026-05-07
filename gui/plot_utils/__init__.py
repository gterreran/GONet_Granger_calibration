from .plot_raw import plot_raw_image
from .plot_full_array import plot_full_array_product
from .plot_grid import plot_grid_array
from .plot_unwrapped import plot_unwrapped_grid, initialize_unwrapped_grid
from .plot_nominal import plot_nominal_grid, initialize_nominal_grid
from .plot_bootstrapping import plot_bootstrapping_grid, initialize_bootstrapping_grid
from .plot_modeling import plot_modeling_results, initialize_modeling_results

pipeline_plotters = {
    "raw-image": plot_raw_image,
    "full-array": plot_full_array_product,
    "grid-points": plot_grid_array,
    "averaged-grid": lambda idx, **kwargs: plot_grid_array(idx, average=True, **kwargs),
    "unwrapped-grid": plot_unwrapped_grid,
    "nominal-grid": plot_nominal_grid,
    "bootstrapping-grid": plot_bootstrapping_grid,
    "modeling-results": plot_modeling_results
}
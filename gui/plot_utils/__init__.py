from .plot_raw import plot_raw_image
from .plot_full_array import plot_full_array_product
from .plot_grid import plot_grid_array

pipeline_plotters = {
    "raw-image": plot_raw_image,
    "full-array": plot_full_array_product,
    "grid-points": plot_grid_array,
    "averaged-grid": lambda idx, **kwargs: plot_grid_array(idx, average=True, **kwargs),
}
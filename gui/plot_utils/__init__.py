from .plot_raw import plot_raw_image
from .plot_full_array import plot_full_array_product 

pipeline_plotters = {
    "raw-image": plot_raw_image,
    "full-array": plot_full_array_product,
}
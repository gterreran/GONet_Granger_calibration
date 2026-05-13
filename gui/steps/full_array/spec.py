# grid_calibration/gui/steps/full_array/spec.py

from __future__ import annotations
from ...workflow import PipelineStepSpec, ProductKind, ProductIO
from .keys import STEP_KEY, REQUIRED_ARRAY_KEYS

product_io = ProductIO(
    step_key=STEP_KEY,
    suffix="_full_array.npz",
    kind=ProductKind.PER_INPUT,
    required_keys=REQUIRED_ARRAY_KEYS,
    allow_pickle=False,
)

def viewer_factory():
    from .plotting import plot_full_array_product
    return plot_full_array_product

def pipeline_factory():
    from .processing import build_full_arrays_for_images
    return build_full_arrays_for_images

pipeline_step = PipelineStepSpec.from_dict({
    "key": STEP_KEY,
    "label": "Build full arrays",
    "order": 1,
    "mode": "batch",
    "product_kind": product_io.kind,
})
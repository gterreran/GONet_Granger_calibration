# grid_calibration/gui/steps/bootstrapping_grid/spec.py
from __future__ import annotations
from ...workflow import PipelineStepSpec, ProductKind, ProductIO
from .keys import STEP_KEY, REQUIRED_ARRAY_KEYS, OPTIONAL_ARRAY_KEYS, DATA_KEY, PARAMS_KEY
from typing import Any
from ...workflow.io_helpers import object_array, maybe_item
from .params import DEFAULT_PARAMETERS

def encode_product(
    **kwargs: Any,
) -> dict[str, Any]:
    # Make sure kwargs contains exactly the keys we expect, and no more.
    if set(kwargs.keys()) != {DATA_KEY, PARAMS_KEY}:
        raise ValueError(f"Expected kwargs to contain exactly the keys {DATA_KEY} and {PARAMS_KEY}, but got {list(kwargs.keys())}")
    data = kwargs.get(DATA_KEY)
    params = kwargs.get(PARAMS_KEY)
    return {
        DATA_KEY: object_array(data),
        PARAMS_KEY: object_array(params),
    }


def decode_product(loaded: dict[str, Any]) -> dict[str, Any]:
    return {
        DATA_KEY: loaded[DATA_KEY].tolist(),
        PARAMS_KEY: maybe_item(
            loaded.get(PARAMS_KEY, object_array(DEFAULT_PARAMETERS.copy()))
        ),
    }

product_io = ProductIO(
    step_key=STEP_KEY,
    suffix="_bootstrapped_grid.npz",
    kind=ProductKind.SINGLETON,
    required_keys=REQUIRED_ARRAY_KEYS,
    optional_keys=OPTIONAL_ARRAY_KEYS,
    allow_pickle=True,
    encode=encode_product,
    decode=decode_product,
)

def viewer_factory():
    from .plotting import plot_bootstrapping_grid
    return plot_bootstrapping_grid

def initialize_factory():
    from .plotting import initialize_bootstrapping_grid
    return initialize_bootstrapping_grid

pipeline_step = PipelineStepSpec.from_dict({
    "key": STEP_KEY,
    "label": "Bootstrapping grids",
    "order": 6,
    "mode": "interactive",
    "product_kind": product_io.kind,
})
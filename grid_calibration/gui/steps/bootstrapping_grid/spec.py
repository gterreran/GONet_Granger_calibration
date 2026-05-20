# grid_calibration/gui/steps/bootstrapping_grid/spec.py
"""
Workflow specification and product descriptor for the bootstrapping-grid step.

The bootstrapping-grid step is an interactive singleton-product step. It
produces a semantic list of assignment records and stores the parameter
dictionary used to create them.
"""

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
    """
    Decode a bootstrapping-grid NPZ payload into semantic Python objects.

    Parameters
    ----------
    loaded : :class:`dict`
        Dictionary returned by the low-level product loader.

    Returns
    -------
    :class:`dict`
        Decoded product dictionary containing assignment records and processing
        parameters.
    """
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
"""
Singleton product descriptor for bootstrapping-grid products.

The descriptor uses custom encode/decode functions because bootstrapped
assignments are semantic Python records rather than plain numerical arrays.
"""

def viewer_factory():
    """
    Return the bootstrapping-grid viewer callable.

    Returns
    -------
    callable
        The :func:`~grid_calibration.gui.steps.bootstrapping_grid.plotting.plot_bootstrapping_grid`
        function.
    """
    """
    Encode semantic bootstrapping payloads for NPZ storage.

    Parameters
    ----------
    **kwargs : :class:`object`
        Keyword payload containing the bootstrapped assignment records and
        parameter dictionary.

    Returns
    -------
    :class:`dict`
        Encoded dictionary suitable for
        :func:`~grid_calibration.gui.workflow.io_helpers.save_npz_dict`.
    """
    from .plotting import plot_bootstrapping_grid
    return plot_bootstrapping_grid

def initialize_factory():
    """
    Return the bootstrapping-grid interactive initialization callable.

    Returns
    -------
    callable
        The
        :func:`~grid_calibration.gui.steps.bootstrapping_grid.plotting.initialize_bootstrapping_grid`
        function.
    """
    from .plotting import initialize_bootstrapping_grid
    return initialize_bootstrapping_grid

pipeline_step = PipelineStepSpec.from_dict({
    "key": STEP_KEY,
    "label": "Bootstrapping grids",
    "order": 6,
    "mode": "interactive",
    "product_kind": product_io.kind,
})
"""
Workflow specification for the bootstrapping-grid step.
"""

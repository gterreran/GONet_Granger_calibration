# grid_calibration/gui/steps/nominal_grid/spec.py
"""
Workflow specification and product descriptor for the nominal-grid step.

The nominal-grid step is an interactive singleton-product step. It consumes the
unwrapped-grid product and produces one ``*_nominal_grid.npz`` file containing
assignment records and the parameter dictionary used to create them.
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
    """
    Encode semantic nominal-grid payloads for NPZ storage.

    Parameters
    ----------
    **kwargs : :class:`object`
        Keyword payload. The keys must be exactly
        :data:`~grid_calibration.gui.steps.nominal_grid.keys.DATA_KEY` and
        :data:`~grid_calibration.gui.steps.nominal_grid.keys.PARAMS_KEY`.

    Returns
    -------
    :class:`dict`
        Encoded dictionary suitable for
        :func:`~grid_calibration.gui.workflow.io_helpers.save_npz_dict`.

    Raises
    ------
    :class:`ValueError`
        If the provided keyword keys do not exactly match the nominal-grid
        product schema.
    """
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
    Decode a loaded nominal-grid NPZ payload into semantic Python objects.

    Parameters
    ----------
    loaded : :class:`dict`
        Dictionary returned by the low-level product loader.

    Returns
    -------
    :class:`dict`
        Decoded product dictionary containing assignment records and parameter
        values. Missing parameter payloads fall back to
        :data:`~grid_calibration.gui.steps.nominal_grid.params.DEFAULT_PARAMETERS`.
    """
    return {
        DATA_KEY: loaded[DATA_KEY].tolist(),
        PARAMS_KEY: maybe_item(
            loaded.get(PARAMS_KEY, object_array(DEFAULT_PARAMETERS.copy()))
        ),
    }


product_io = ProductIO(
    step_key=STEP_KEY,
    suffix="_nominal_grid.npz",
    kind=ProductKind.SINGLETON,
    required_keys=REQUIRED_ARRAY_KEYS,
    optional_keys=OPTIONAL_ARRAY_KEYS,
    allow_pickle=True,
    encode=encode_product,
    decode=decode_product,
)
"""
Singleton product descriptor for nominal-grid products.

The descriptor uses custom encode/decode functions because nominal-grid
assignments are semantic Python records rather than plain numerical arrays.
"""

def viewer_factory():
    """
    Return the nominal-grid viewer callable.

    Returns
    -------
    callable
        The :func:`~grid_calibration.gui.steps.nominal_grid.plotting.plot_nominal_grid`
        function.
    """
    from .plotting import plot_nominal_grid
    return plot_nominal_grid

def initialize_factory():
    """
    Return the nominal-grid interactive initialization callable.

    Returns
    -------
    callable
        The
        :func:`~grid_calibration.gui.steps.nominal_grid.plotting.initialize_nominal_grid`
        function.
    """
    from .plotting import initialize_nominal_grid
    return initialize_nominal_grid

pipeline_step = PipelineStepSpec.from_dict({
    "key": STEP_KEY,
    "label": "Build nominal grids",
    "order": 5,
    "mode": "interactive",
    "product_kind": product_io.kind,
})
"""
Workflow specification for the nominal-grid step.
"""

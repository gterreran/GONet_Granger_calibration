# grid_calibration/gui/steps/modeling_results/spec.py
"""
Workflow specification and product descriptor for the modeling-results step.

The modeling-results step is an interactive singleton-product step. It consumes
the bootstrapped assignment records and produces one ``*_modeling_results.npz``
product containing the fitted model result and parameter dictionary.
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
    Encode semantic modeling-result payloads for NPZ storage.

    Parameters
    ----------
    **kwargs : :class:`object`
        Keyword payload. The keys must be exactly
        :data:`~grid_calibration.gui.steps.modeling_results.keys.DATA_KEY` and
        :data:`~grid_calibration.gui.steps.modeling_results.keys.PARAMS_KEY`.

    Returns
    -------
    :class:`dict`
        Encoded dictionary suitable for
        :func:`~grid_calibration.gui.workflow.io_helpers.save_npz_dict`.

    Raises
    ------
    :class:`ValueError`
        If the provided keyword keys do not exactly match the modeling-results
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
    Decode a loaded modeling-results NPZ payload into semantic Python objects.

    Parameters
    ----------
    loaded : :class:`dict`
        Dictionary returned by the low-level product loader.

    Returns
    -------
    :class:`dict`
        Decoded product dictionary containing the fit result and parameter
        dictionary. Missing parameters fall back to
        :data:`~grid_calibration.gui.steps.modeling_results.params.DEFAULT_PARAMETERS`.
    """
    return {
        DATA_KEY: maybe_item(loaded[DATA_KEY]),
        PARAMS_KEY: maybe_item(
            loaded.get(PARAMS_KEY, object_array(DEFAULT_PARAMETERS.copy()))
        ),
    }

product_io = ProductIO(
    step_key=STEP_KEY,
    suffix="_modeling_results.npz",
    kind=ProductKind.SINGLETON,
    required_keys=REQUIRED_ARRAY_KEYS,
    optional_keys=OPTIONAL_ARRAY_KEYS,
    allow_pickle=True,
    encode=encode_product,
    decode=decode_product,
)
"""
Singleton product descriptor for modeling-results products.

The descriptor uses custom encode/decode hooks because the fit result is a
semantic Python object rather than a plain numerical array.
"""

def viewer_factory():
    """
    Return the modeling-results viewer callable.

    Returns
    -------
    callable
        The
        :func:`~grid_calibration.gui.steps.modeling_results.plotting.plot_modeling_results`
        function.
    """
    from .plotting import plot_modeling_results
    return plot_modeling_results

def initialize_factory():
    """
    Return the modeling-results interactive initialization callable.

    Returns
    -------
    callable
        The
        :func:`~grid_calibration.gui.steps.modeling_results.plotting.initialize_modeling_results`
        function.
    """
    from .plotting import initialize_modeling_results
    return initialize_modeling_results

pipeline_step = PipelineStepSpec.from_dict({
    "key": STEP_KEY,
    "label": "Modeling",
    "order": 7,
    "mode": "interactive",
    "product_kind": product_io.kind,
})
"""
Workflow specification for the modeling-results step.
"""

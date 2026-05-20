# grid_calibration/gui/workflow/registry.py
"""
Central registry for grid-calibration workflow steps.

This module imports the step packages listed in
:data:`grid_calibration.gui.steps.STEP_MODULES` and builds the runtime
registries used by the Dash GUI, product-discovery system, and pipeline
callbacks.

The registry is intentionally constructed at import time. Each step package is
expected to expose two public objects:

``pipeline_step``
    A :class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec` describing
    the workflow metadata for the step.

``product_io``
    A :class:`~grid_calibration.gui.workflow.product_io.ProductIO` instance, or
    ``None`` for steps that do not create a persisted product.

Keeping registration centralized gives the rest of the GUI a single source of
truth for step order, product contracts, button enable rules, row clickability,
and optional step-specific callback modules.

Raises
------
RuntimeError
    Raised during import if a step module does not expose the required
    ``pipeline_step`` or ``product_io`` object, if two steps use the same key, or
    if a step's :class:`~grid_calibration.gui.workflow.product_io.ProductIO`
    uses a different key from its
    :class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec`.
"""

from __future__ import annotations

import importlib
from ..steps import STEP_MODULES
from .specs import PipelineStepSpec
from .product_io import ProductIO


#: Mapping from step key to :class:`~grid_calibration.gui.workflow.specs.PipelineStepSpec`.
#:
#: This dictionary is populated at import time from
#: :data:`grid_calibration.gui.steps.STEP_MODULES`.
STEP_BY_ID: dict[str, PipelineStepSpec] = {}
#: Mapping from step key to :class:`~grid_calibration.gui.workflow.product_io.ProductIO`.
#:
#: Entries may be ``None`` for steps that do not persist a product.
PRODUCT_IO_BY_STEP: dict[str, ProductIO] = {}


for module in STEP_MODULES:
    try:
        step: PipelineStepSpec = getattr(module, "pipeline_step")
    except AttributeError as exc:
        raise RuntimeError(
            f"Step module {module.__name__!r} does not expose pipeline_step."
        ) from exc

    if step.key in STEP_BY_ID:
        raise RuntimeError(f"Duplicate pipeline step key: {step.key!r}")

    STEP_BY_ID[step.key] = step

    try:
        product: ProductIO  = getattr(module, "product_io")
    except AttributeError as exc:
        raise RuntimeError(
            f"Step module {module.__name__!r} does not expose product_io."
        ) from exc
    
    if product is not None and product.step_key != step.key:
        raise RuntimeError(
            f"ProductIO key mismatch for step {step.key!r}: "
            f"got product.step_key={product.step_key!r}"
        )

    PRODUCT_IO_BY_STEP[step.key] = product


#: Workflow step specifications sorted by their numeric order.
ORDERED_STEP_SPECS = sorted(STEP_BY_ID.values(), key=lambda step: step.order)
#: Ordered list of workflow step keys.
ORDERED_STEPS = [step.key for step in ORDERED_STEP_SPECS]
#: Ordered list of executable steps, excluding the raw-image viewer step.
RUNNABLE_STEPS = ORDERED_STEPS[1:]


def enabled_for_step(step_key: str):
    """
    Build a button-enable predicate for one workflow step.

    A step is enabled when the immediately preceding step has an available
    product in the session product registry. The first step is always enabled
    because it represents the raw image viewer rather than a generated product.

    Parameters
    ----------
    step_key : :class:`str`
        Key of the step for which the enable rule should be created. The key
        must be present in :data:`ORDERED_STEPS`.

    Returns
    -------
    :class:`collections.abc.Callable`
        Predicate accepting the session product mapping and returning ``True``
        when the step's run button should be enabled.

    Raises
    ------
    ValueError
        Raised if ``step_key`` is not present in :data:`ORDERED_STEPS`.
    """
    index = ORDERED_STEPS.index(step_key)

    if index == 0:
        return lambda products: True

    previous_key = ORDERED_STEPS[index - 1]
    return lambda products: bool(products.get(previous_key))


def clickable_for_step(step_key: str):
    """
    Build a row-click predicate for one workflow step.

    Clickability is intentionally based on the step's own product rather than
    the previous step's product. This allows users to revisit previously
    generated products while preventing the GUI from opening viewers for steps
    with no registered output.

    Parameters
    ----------
    step_key : :class:`str`
        Key of the step for which the clickability rule should be created.

    Returns
    -------
    :class:`collections.abc.Callable`
        Predicate accepting the session product mapping and returning ``True``
        when the step row should respond to clicks.
    """
    return lambda products: bool(products.get(step_key))


#: Mapping from step key to a predicate controlling whether that step's run
#: button should be enabled for the current product registry.
ENABLE_RULES = {
    step_key: enabled_for_step(step_key)
    for step_key in ORDERED_STEPS
}

#: Mapping from step key to a predicate controlling whether that step row can
#: be clicked/viewed for the current product registry.
CLICKABLE_RULES = {
    step_key: clickable_for_step(step_key)
    for step_key in ORDERED_STEPS
}


def import_step_callback_modules():
    """
    Import optional callback modules exposed by step packages.

    Each registered step package may provide a sibling ``callbacks`` module.
    This function imports those modules for their side effects so that
    step-specific Dash callbacks can register themselves with the application.
    Missing callback modules are ignored, but import errors raised *inside* a
    callback module are allowed to propagate.

    Returns
    -------
    :class:`list`
        Imported callback modules, in the same order as
        :data:`grid_calibration.gui.steps.STEP_MODULES`.

    Raises
    ------
    ModuleNotFoundError
        Propagated when a callback module exists but one of its internal imports
        fails.
    """
    modules = []

    for module in STEP_MODULES:
        callback_module_name = f"{module.__name__}.callbacks"

        try:
            callback_module = importlib.import_module(callback_module_name)

        except ModuleNotFoundError as exc:
            if exc.name != callback_module_name:
                raise

        else:
            modules.append(callback_module)

    return modules
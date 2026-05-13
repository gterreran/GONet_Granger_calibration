# grid_calibration/gui/workflow/registry.py

from __future__ import annotations

import importlib
from ..steps import STEP_MODULES
from .specs import PipelineStepSpec
from .product_io import ProductIO


STEP_BY_ID: dict[str, PipelineStepSpec] = {}
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


ORDERED_STEP_SPECS = sorted(STEP_BY_ID.values(), key=lambda step: step.order)
ORDERED_STEPS = [step.key for step in ORDERED_STEP_SPECS]
RUNNABLE_STEPS = ORDERED_STEPS[1:]


def enabled_for_step(step_key: str):
    """
    Return a rule that enables a step if the previous step has a product.
    """
    index = ORDERED_STEPS.index(step_key)

    if index == 0:
        return lambda products: True

    previous_key = ORDERED_STEPS[index - 1]
    return lambda products: bool(products.get(previous_key))


def clickable_for_step(step_key: str):
    """
    Return a rule that makes a step clickable if its own product exists.
    """
    return lambda products: bool(products.get(step_key))


ENABLE_RULES = {
    step_key: enabled_for_step(step_key)
    for step_key in ORDERED_STEPS
}

CLICKABLE_RULES = {
    step_key: clickable_for_step(step_key)
    for step_key in ORDERED_STEPS
}


def import_step_callback_modules():
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
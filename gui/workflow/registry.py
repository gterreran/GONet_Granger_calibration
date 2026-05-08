# grid_calibration/gui/workflow/registry.py

import importlib
import pkgutil
from .. import steps

STEPS = []

for module_info in pkgutil.iter_modules(steps.__path__):
    module = importlib.import_module(f"{steps.__name__}.{module_info.name}.spec")
    if hasattr(module, "pipeline_step"):
        STEPS.append(module.pipeline_step)


STEPS = sorted(STEPS, key=lambda s: s.order)

STEP_BY_ID = {s.key: s for s in STEPS}
ORDERED_STEPS = [s.key for s in STEPS]
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

VIEWER_FUNCS = {
    step.key: step.viewer_func
    for step in STEPS
    if step.viewer_func is not None
}

PRODUCT_SPECS = {
    step.key: step.product
    for step in STEPS
    if step.product is not None
}

def import_step_callback_modules():
    modules = []

    for module_info in pkgutil.iter_modules(steps.__path__):
        package_name = f"{steps.__name__}.{module_info.name}"

        try:
            module = importlib.import_module(f"{package_name}.callbacks")
        except ModuleNotFoundError as exc:
            if exc.name != f"{package_name}.callbacks":
                raise
        else:
            modules.append(module)

    return modules
# grid_calibration/gui/workflow/specs.py

from __future__ import annotations

import inspect
from dataclasses import dataclass
from .product_io import ProductKind
from typing import Any, Callable, Literal, Optional


StepMode = Literal["batch", "interactive"]
OptionKind = Literal["dropdown", "label"]

StepCallable = Callable[..., Any]
StepCallableFactory = Callable[[], StepCallable]


@dataclass(frozen=True)
class PipelineStepSpec:
    key: str
    label: str
    order: int
    mode: StepMode

    option_kind: OptionKind

    viewer_factory: Optional[StepCallableFactory] = None
    pipeline_factory: Optional[StepCallableFactory] = None
    initialize_factory: Optional[StepCallableFactory] = None

    @property
    def button_label(self) -> str:
        return f"{self.order}. {self.label}"

    @property
    def viewer_func(self) -> Optional[StepCallable]:
        if self.viewer_factory is None:
            return None

        return self.viewer_factory()

    @property
    def pipeline_func(self) -> Optional[StepCallable]:
        if self.pipeline_factory is None:
            return None

        return self.pipeline_factory()

    @property
    def initialize_interactive_state(self) -> Optional[StepCallable]:
        if self.initialize_factory is None:
            return None

        return self.initialize_factory()
    
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PipelineStepSpec":
        """
        Create a PipelineStepSpec instance from a dictionary.

        The dictionary should contain the following keys:
        - "key": a unique string identifier for the step
        - "label": a human-readable label for the step
        - "order": an integer specifying the order of the step in the pipeline
        - "mode": either "batch" or "interactive", specifying how the step is executed
        - "product_kind": a ProductKind value specifying the kind of product produced by the step
        
        Note that the dictionary is expected to contain a "product_kind" key
        containing a :class:`~.ProductKind` value, instead of the "option_kind"
        key that :class:`PipelineStepSpec` actually uses. The option_kind argument
        is derived from the product_kind value: if the product kind is PER_INPUT,
        then option_kind is "dropdown", otherwise it's "label".
        This allows step specifications to be defined in a more concise way, without
        having to specify the option_kind explicitly.

        Parameters
        ----------
        :class:`dict`
            A dictionary containing the step specification.

        Returns
        -------
        :class:`PipelineStepSpec`
            An instance of PipelineStepSpec created from the dictionary.

        """
        caller_globals = inspect.currentframe().f_back.f_globals
        
        product_kind = d.get("product_kind")
        if product_kind is None or product_kind is ProductKind.PER_INPUT:
            option_kind = "dropdown"
        else:
            option_kind = "label"

        return cls(
            key=d["key"],
            label=d["label"],
            order=d["order"],
            mode=d["mode"],
            option_kind=option_kind,
            viewer_factory=caller_globals.get("viewer_factory"),
            pipeline_factory=caller_globals.get("pipeline_factory"),
            initialize_factory=caller_globals.get("initialize_factory"),
        )

    def __str__(self) -> str:
        return self.key
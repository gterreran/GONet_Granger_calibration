# grid_calibration/gui/workflow/specs.py

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Optional, Callable, Any
from enum import Enum, auto
from pathlib import Path

class ProductKind(Enum):
    PER_INPUT = auto()   # depends on input filename stem
    SINGLETON = auto()   # exactly one file per run


@dataclass(frozen=True)
class ProductSpec:
    suffix: str
    kind: ProductKind

    def path(self, input_file: Path)-> Path:
        if self.kind is ProductKind.SINGLETON:
            root = '_'.join(input_file.stem.split("_")[:3])
            return Path(f"{root}{self.suffix}")
        else:
            return Path(f"{input_file.stem}{self.suffix}")
    

StepMode = Literal["batch", "interactive"]
OptionKind = Literal["dropdown", "label"]

@dataclass(frozen=True)
class PipelineStepSpec:
    key: str
    label: str
    order: int
    mode: StepMode                    # "batch" | "interactive"

    viewer_func: Callable[..., Any]
    product: Optional[ProductSpec] = None
    pipeline_func: Optional[Callable] = None # for non-interactive steps
    initialize_interactive_state: Optional[Callable] = None # for interactive steps

    @property
    def button_label(self) -> str:
        return f"{self.order}. {self.label}"
    
    @property
    def option_kind(self) -> OptionKind:
        if self.product is None or self.product.kind == ProductKind.PER_INPUT:
            return "dropdown"
        else:
            return "label"

    @classmethod
    def from_dict(cls, d: dict) -> PipelineStepSpec:
        product_data = d.get("product")

        if isinstance(product_data, ProductSpec):
            product = product_data
        elif isinstance(product_data, dict):
            product = ProductSpec(**product_data)
        elif product_data is None:
            product = None
        else:
            raise TypeError(
                f"Invalid product specification for step {d['key']!r}: "
                f"expected ProductSpec, dict, or None, got {type(product_data).__name__}"
            )

        return cls(
            key=d["key"],
            label=d["label"],
            order=d["order"],
            mode=d["mode"],
            product=product,
            viewer_func=d["viewer_func"],
            pipeline_func=d.get("pipeline_func"),
            initialize_interactive_state=d.get("initialize_interactive_state"),
        )

    def __str__(self) -> str:
        return self.key
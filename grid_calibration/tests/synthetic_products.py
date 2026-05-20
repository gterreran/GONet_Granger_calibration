from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from grid_calibration.gui.workflow.product_io import ProductIO


@dataclass
class SyntheticSession:
    raw_files: list[Path]
    output_dir: Path
    products: dict[str, Any] = field(default_factory=dict)

    @property
    def first_raw_file(self) -> Path:
        return self.raw_files[0]

    def get(self, step: str) -> Any:
        return self.products.get(step)

    def set(self, step: str, value: Any) -> None:
        self.products[step] = value


def nominal_records() -> list[dict[str, Any]]:
    return [
        {
            "idx": 0,
            "pixel_x": 100.0,
            "pixel_y": 100.0,
            "theta": 0.0,
            "r": 10.0,
            "nominal_r": 2.5,
            "nominal_theta": 0.0,
            "circle_index": 0,
            "spoke_index": 0,
        },
        {
            "idx": 1,
            "pixel_x": 110.0,
            "pixel_y": 100.0,
            "theta": 90.0,
            "r": 10.0,
            "nominal_r": 2.5,
            "nominal_theta": 90.0,
            "circle_index": 0,
            "spoke_index": 1,
        },
        {
            "idx": 2,
            "pixel_x": 100.0,
            "pixel_y": 110.0,
            "theta": 0.0,
            "r": 20.0,
            "nominal_r": 5.0,
            "nominal_theta": 0.0,
            "circle_index": 1,
            "spoke_index": 0,
        },
        {
            "idx": 3,
            "pixel_x": 110.0,
            "pixel_y": 110.0,
            "theta": 90.0,
            "r": 20.0,
            "nominal_r": 5.0,
            "nominal_theta": 90.0,
            "circle_index": 1,
            "spoke_index": 1,
        },
    ]


def minimal_arrays_for_product(product: ProductIO) -> dict[str, Any]:
    step_key = product.step_key

    if step_key == "full-array":
        arrays: dict[str, Any] = {}
        for key in product.required_keys:
            if key == "image":
                arrays[key] = np.arange(100, dtype=float).reshape(10, 10)
            elif "bins" in key:
                arrays[key] = np.array([0.0, 1.0], dtype=float)
            else:
                arrays[key] = np.array([1.0], dtype=float)
        return arrays

    if step_key == "grid-points":
        return {"grid": np.array([[2.0, 3.0], [4.0, 5.0], [6.0, 7.0]])}

    if step_key == "averaged-grid":
        return {
            "grid": np.array([[2.0, 3.0], [4.0, 5.0], [6.0, 7.0]]),
            "counts": np.array([2, 2, 1]),
        }

    if step_key == "unwrapped-grid":
        return {
            "idx": np.array([0, 1, 2, 3], dtype=int),
            "theta": np.array([0.0, 90.0, 0.0, 90.0], dtype=float),
            "r": np.array([10.0, 10.0, 20.0, 20.0], dtype=float),
            "pts": np.array([[100.0, 100.0], [110.0, 100.0], [100.0, 110.0], [110.0, 110.0]]),
            "center": np.array([105.0, 105.0], dtype=float),
        }

    if step_key in {"nominal-grid", "bootstrapping-grid"}:
        return {
            product.required_keys[0]: nominal_records(),
            "params": {"synthetic": True},
        }

    if step_key == "modeling-results":
        return {
            product.required_keys[0]: {"success": True, "rms": 0.0},
            "params": {"synthetic": True},
        }

    raise AssertionError(f"No synthetic payload defined for {step_key!r}.")


def write_product(product: ProductIO, path: Path) -> Path:
    product.clear_cache()
    return product.save(path=path, **minimal_arrays_for_product(product))

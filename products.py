from __future__ import annotations
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Iterable, Optional, List, Dict, Any


class ProductKind(Enum):
    PER_INPUT = auto()   # depends on input filename stem
    SINGLETON = auto()   # exactly one file per run


@dataclass(frozen=True)
class ProductSpec:
    name: str
    suffix: str
    kind: ProductKind

    def path(self, input_file: Optional[Path] = None) -> Path:
        if self.kind is ProductKind.SINGLETON:
            return Path(self.suffix)
        else:
            return Path(f"{input_file.stem}{self.suffix}")


# Definition of known products
FULL_ARRAY = ProductSpec(
    name="full-array",
    suffix="_full_array.npz",
    kind=ProductKind.PER_INPUT,
)

GRID_POINTS = ProductSpec(
    name="grid-points",
    suffix="_grid_points.npz",
    kind=ProductKind.PER_INPUT,
)

AVERAGED_GRID = ProductSpec(
    name="averaged-grid",
    suffix="averaged_grid.npz",
    kind=ProductKind.SINGLETON,
)

CALIBRATED_GRID = ProductSpec(
    name="calibrated-grid",
    suffix="calibrated_grid.npz",
    kind=ProductKind.SINGLETON,
)

ALL_PRODUCTS = (FULL_ARRAY, GRID_POINTS, AVERAGED_GRID, CALIBRATED_GRID)
ALL_PRODUCTS = {
    p.name: p
    for p in ALL_PRODUCTS
}

def discover_products(
    input_files: Iterable[Path],
    outdir: Path,
) -> Dict[str, List[Path]]:
    """
    Discover pipeline products in `outdir` corresponding to `input_files`.

    Parameters
    ----------
    input_files
        Iterable of input image paths (e.g. *.jpg).
    outdir
        Directory where pipeline products are stored.

    Returns
    -------
    dict
        Mapping:
            product_name -> list of Paths

        For singleton products, the list has length 0 or 1.
        For per-input products, the list may contain multiple files.
    """
    outdir = Path(outdir)

    results: Dict[str, Any] = {}

    for name in ALL_PRODUCTS.keys():
        results[name] = [] if ALL_PRODUCTS[name].kind is ProductKind.PER_INPUT else None


    for product in ALL_PRODUCTS.values():
        if product.kind is ProductKind.SINGLETON:
            path = outdir / product.path()
            if path.exists():
                results[product.name] = path

        else:
            for infile in input_files:
                path = outdir / product.path(infile)
                if path.exists():
                    results[product.name].append(path)

    return results
# grid_calibration/gui/session.py

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Iterable
from dash import Dash
from .workflow.registry import PRODUCT_SPECS
from .workflow.specs import ProductKind

from ..errors import PipelineStepError, MissingProductError, GridCalibrationError

def get_session() -> CalibrationSession:
    """
    Return the active calibration session.
    """
    from .server import app  # local import avoids circular import issues

    try:
        return app.server.config["session"]
    except KeyError as exc:
        raise GridCalibrationError(
            "No CalibrationSession is attached to the Dash app."
        ) from exc

@dataclass
class CalibrationSession:
    raw_files: list[Path]
    output_dir: Path
    products: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_inputs(
        cls,
        raw_files: list[Path],
        output_dir: Path,
    ) -> "CalibrationSession":
        raw_files = [Path(p) for p in raw_files]
        output_dir = Path(output_dir)

        products = {
            "raw-image": raw_files,
        }
        products.update(discover_products(raw_files, output_dir))

        return cls(
            raw_files=raw_files,
            output_dir=output_dir,
            products=products,
        )

    def get(self, step: str) -> Any:
        return self.products.get(step)

    def set(self, step: str, value: Any) -> None:
        self.products[step] = value

    def has(self, step: str) -> bool:
        value = self.get(step)
        if isinstance(value, list):
            return len(value) > 0
        return value is not None

    def require(self, step: str) -> Any:
        value = self.get(step)
        if value is None:
            raise MissingProductError(f"Missing required product: {step!r}")
        return value

    @property
    def first_raw_file(self) -> Path:
        if not self.raw_files:
            raise PipelineStepError("CalibrationSession has no raw files.")
        return self.raw_files[0]

    def refresh_products(self) -> None:
        self.products.update(discover_products(self.raw_files, self.output_dir))

    def expected_path(self, step: str, input_file: Path | None = None) -> Path:
        if step not in PRODUCT_SPECS:
            raise MissingProductError(f"No product is registered for step {step!r}")

        spec = PRODUCT_SPECS[step]
        input_file = input_file or self.first_raw_file
        return self.output_dir / spec.path(input_file)
    
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

    input_files = [Path(p) for p in input_files]

    if not input_files:
        raise PipelineStepError("discover_products requires at least one input file.")

    outdir = Path(outdir)
    results: dict[str, Any] = {}

    for key, spec in PRODUCT_SPECS.items():
        results[key] = [] if spec.kind is ProductKind.PER_INPUT else None

    for key, spec in PRODUCT_SPECS.items():
        if spec.kind is ProductKind.SINGLETON:
            path = outdir / spec.path(input_file=input_files[0])
            if path.exists():
                results[key] = path
        else:
            for infile in input_files:
                path = outdir / spec.path(input_file=infile)
                if path.exists():
                    results[key].append(path)

    return results
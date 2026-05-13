# grid_calibration/gui/session.py

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .workflow.registry import PRODUCT_IO_BY_STEP
from .workflow.product_io import discover_products
from ..errors import PipelineStepError, GridCalibrationError


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
        products.update(
            discover_products(
                PRODUCT_IO_BY_STEP,
                raw_files,
                output_dir,
            )
        )

        return cls(
            raw_files=raw_files,
            output_dir=output_dir,
            products=products,
        )

    @property
    def first_raw_file(self) -> Path:
        if not self.raw_files:
            raise PipelineStepError("CalibrationSession has no raw files.")
        return self.raw_files[0]

    def get(self, step: str) -> Any:
        return self.products.get(step)

    def set(self, step: str, value: Any) -> None:
        self.products[step] = value

    def refresh_products(self) -> None:
        self.products.update(
            discover_products(
                PRODUCT_IO_BY_STEP,
                self.raw_files,
                self.output_dir,
            )
        )
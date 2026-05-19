from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .....errors import ProductLoadError

@dataclass
class GridData:
    """Measured and nominal grid point data."""

    idx: np.ndarray
    x: np.ndarray
    y: np.ndarray
    r_meas: np.ndarray
    theta_meas_deg: np.ndarray
    r_nom_deg: np.ndarray
    theta_nom_deg: np.ndarray

    @classmethod
    def from_records(cls, raw: list[dict]) -> "GridData":
        """
        Build grid data from nominal-assignment records.
        """
        if isinstance(raw, np.ndarray):
            raw = raw.tolist()

        if isinstance(raw, dict):
            raw = [raw]

        if not isinstance(raw, list) or not raw:
            raise ProductLoadError(
                "GridData records must be a non-empty list of dictionaries."
            )

        try:
            idx = np.array([row.get("idx", i) for i, row in enumerate(raw)], dtype=int)
            x = np.array([row["pixel_x"] for row in raw], dtype=float)
            y = np.array([row["pixel_y"] for row in raw], dtype=float)
            r_meas = np.array([row["r"] for row in raw], dtype=float)
            theta_meas_deg = np.array([row["theta"] for row in raw], dtype=float)
            r_nom_deg = np.array([row["nominal_r"] for row in raw], dtype=float)
            theta_nom_deg = np.array([row["nominal_theta"] for row in raw], dtype=float)
        except Exception as exc:
            raise ProductLoadError(
                "Could not parse required keys from nominal-assignment records."
            ) from exc

        finite = (
            np.isfinite(x)
            & np.isfinite(y)
            & np.isfinite(r_meas)
            & np.isfinite(theta_meas_deg)
            & np.isfinite(r_nom_deg)
            & np.isfinite(theta_nom_deg)
        )

        return cls(
            idx=idx[finite],
            x=x[finite],
            y=y[finite],
            r_meas=r_meas[finite],
            theta_meas_deg=theta_meas_deg[finite],
            r_nom_deg=r_nom_deg[finite],
            theta_nom_deg=theta_nom_deg[finite],
        )

    def subset(self, mask: np.ndarray) -> "GridData":
        """Return a subset of the grid data."""
        mask = np.asarray(mask, dtype=bool)
        return GridData(
            idx=self.idx[mask],
            x=self.x[mask],
            y=self.y[mask],
            r_meas=self.r_meas[mask],
            theta_meas_deg=self.theta_meas_deg[mask],
            r_nom_deg=self.r_nom_deg[mask],
            theta_nom_deg=self.theta_nom_deg[mask],
        )


"""
Data containers used by bootstrapping-grid processing.

The dataclasses in this module provide typed containers for dense detections,
mutable nominal assignments, and per-spoke bootstrap results.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .....errors import DetectionError

@dataclass
class DenseGrid:
    """Dense set of detected grid points without nominal labels."""

    idx: np.ndarray
    x: np.ndarray
    y: np.ndarray

    @classmethod
    def load(cls, data: np.ndarray) -> "DenseGrid":
        """
        Load a dense grid from an ``(N, 2)`` array.

        Parameters
        ----------
        data
            Dense grid array. The expected convention is ``[row, col]`` or
            ``[y, x]`` per point.

        Returns
        -------
        DenseGrid
            Dense grid with explicit ``x`` and ``y`` arrays.
        """
        grid = np.asarray(data, dtype=float)
        if grid.ndim != 2 or grid.shape[1] != 2:
            raise DetectionError("Dense grid must have shape (N, 2).")

        return cls(
            idx=np.arange(grid.shape[0], dtype=int),
            x=grid[:, 1].astype(float),
            y=grid[:, 0].astype(float),
        )

    @property
    def xy(self) -> np.ndarray:
        """Return points as an ``(N, 2)`` array in ``x, y`` order."""
        return np.column_stack([self.x, self.y])


@dataclass
class GridData:
    """Mutable set of nominal grid assignments."""

    idx: np.ndarray
    x: np.ndarray
    y: np.ndarray
    r_nom_deg: np.ndarray
    theta_nom_deg: np.ndarray

    def __post_init__(self) -> None:
        self.rebuild_index()

    @classmethod
    def load(cls, data: np.ndarray) -> "GridData":
        """
        Load confidently labeled intersections from an ``.npz`` ``data`` entry.
        """
        rows = list(data)
        rows.sort(key=lambda r: int(r.get("idx", -1)))

        return cls(
            idx=np.array([row.get("idx", i) for i, row in enumerate(rows)], dtype=int),
            x=np.array([row["pixel_x"] for row in rows], dtype=float),
            y=np.array([row["pixel_y"] for row in rows], dtype=float),
            r_nom_deg=np.array([row["nominal_r"] for row in rows], dtype=float),
            theta_nom_deg=np.array([row["nominal_theta"] % 360.0 for row in rows], dtype=float),
        )

    def rebuild_index(self) -> None:
        """Rebuild the ``idx -> array position`` map."""
        self._idx_map: dict[int, int] = {int(v): i for i, v in enumerate(self.idx)}

    def has_idx(self, idx: int) -> bool:
        """Return whether ``idx`` is present."""
        return int(idx) in self._idx_map

    def position(self, idx: int) -> int:
        """Return array position for a dense-point index."""
        return self._idx_map[int(idx)]

    def get_theta(self, idx: int) -> float:
        """Return nominal theta for one point."""
        return float(self.theta_nom_deg[self.position(idx)])

    def get_radius(self, idx: int) -> float:
        """Return nominal radius for one point."""
        return float(self.r_nom_deg[self.position(idx)])

    def set_theta(self, idx: int, theta_deg: float) -> None:
        """Set nominal theta for one point."""
        self.theta_nom_deg[self.position(idx)] = theta_deg

    def set_radius(self, idx: int, r_deg: float) -> None:
        """Set nominal radius for one point."""
        self.r_nom_deg[self.position(idx)] = r_deg

    def clear_assignment(self, idx: int) -> None:
        """Clear both nominal radius and theta for one point."""
        pos = self.position(idx)
        self.r_nom_deg[pos] = np.nan
        self.theta_nom_deg[pos] = np.nan

    def append(
        self,
        *,
        idx: int,
        x: float,
        y: float,
        r_nom_deg: float = np.nan,
        theta_nom_deg: float = np.nan,
    ) -> None:
        """Append a new assigned point."""
        idx = int(idx)
        if idx in self._idx_map:
            raise DetectionError(f"Element with idx={idx} already exists.")

        self.idx = np.append(self.idx, idx)
        self.x = np.append(self.x, float(x))
        self.y = np.append(self.y, float(y))
        self.r_nom_deg = np.append(self.r_nom_deg, float(r_nom_deg))
        self.theta_nom_deg = np.append(self.theta_nom_deg, float(theta_nom_deg))
        self._idx_map[idx] = self.idx.size - 1

    def add_or_update(
        self,
        *,
        idx: int,
        x: float,
        y: float,
        r_nom_deg: float | None = None,
        theta_nom_deg: float | None = None,
    ) -> None:
        """Add a point or update existing nominal fields."""
        if self.has_idx(idx):
            pos = self.position(idx)
            if r_nom_deg is not None:
                self.r_nom_deg[pos] = r_nom_deg
            if theta_nom_deg is not None:
                self.theta_nom_deg[pos] = theta_nom_deg
        else:
            self.append(
                idx=idx,
                x=x,
                y=y,
                r_nom_deg=np.nan if r_nom_deg is None else r_nom_deg,
                theta_nom_deg=np.nan if theta_nom_deg is None else theta_nom_deg,
            )


@dataclass
class SpokeBootstrapResult:
    """Result from bootstrapping one opposite-spoke pair."""

    spoke_deg: float
    opposite_deg: float
    seed_count: int
    assigned_idx: np.ndarray
    assigned_x: np.ndarray
    assigned_y: np.ndarray
    assigned_side: np.ndarray
    curve_x: np.ndarray
    curve_y: np.ndarray
    curve_u: np.ndarray
    inward_growth_steps: int
    outward_growth_steps: int
    cutoff_nominal_r_deg: float
    cutoff_pix: float

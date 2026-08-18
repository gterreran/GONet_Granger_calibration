"""
Polar radial/tangential distortion model definition.

The model predicts image-space coordinates from nominal polar grid coordinates
using a symmetric radial polynomial plus harmonic radial and tangential
correction fields.
"""

from __future__ import annotations

import numpy as np

from grid_calibration.distortion import evaluate_polar_distortion

from .config import ModelConfig
from .data import GridData
from .utils import cartesian_center_from_measured_polar, circ_median_deg


class PolarDistortionModel:
    """
    Symmetric plus radial/tangential harmonic distortion model.

    Parameters
    ----------
    config : :class:`~grid_calibration.gui.steps.modeling_results.processing.config.ModelConfig`
        Model-basis configuration.
    r_nom_max_deg : :class:`float`
        Maximum nominal grid radius in degrees, used to normalize the harmonic
        correction basis.

    Returns
    -------
    :class:`PolarDistortionModel`
        Model instance with parameter names and basis dimensions initialized.
    """

    def __init__(self, config: ModelConfig, r_nom_max_deg: float) -> None:
        self.config = config
        self.r_nom_max_deg = float(r_nom_max_deg)

        self.sym_names = ["cx", "cy", "theta0_deg"]
        self.sym_names += [f"k{p}" for p in range(1, config.radial_degree + 1)]

        self.field_names: list[str] = []
        start_n = 0 if config.fit_constant_terms else 1
        for axis in ("dr", "dtan"):
            for m in range(0, config.harmonic_radial_degree + 1):
                for n in range(start_n, config.harmonic_order + 1):
                    if n == 0:
                        self.field_names.append(f"{axis}_m{m}_c0")
                    else:
                        self.field_names.append(f"{axis}_m{m}_c{n}")
                        self.field_names.append(f"{axis}_m{m}_s{n}")

        self.param_names = self.sym_names + self.field_names
        self.n_sym = len(self.sym_names)
        self.n_total = len(self.param_names)

    def initial_parameters(self, data: GridData) -> np.ndarray:
        """Build an initial parameter vector."""
        cx0, cy0 = cartesian_center_from_measured_polar(
            x=data.x,
            y=data.y,
            r=data.r_meas,
            theta_deg=data.theta_meas_deg,
        )
        theta0_deg = circ_median_deg(data.theta_meas_deg - data.theta_nom_deg)

        u = np.deg2rad(data.r_nom_deg)
        A = np.column_stack([u**p for p in range(1, self.config.radial_degree + 1)])
        coeffs, *_ = np.linalg.lstsq(A, data.r_meas, rcond=None)

        params = np.zeros(self.n_total, dtype=float)
        params[0] = cx0
        params[1] = cy0
        params[2] = theta0_deg
        params[3 : 3 + len(coeffs)] = coeffs
        return params

    def _basis(self, s: np.ndarray, phi: np.ndarray) -> np.ndarray:
        """Build the Fourier-polynomial design matrix for one scalar field."""
        cols: list[np.ndarray] = []
        start_n = 0 if self.config.fit_constant_terms else 1
        for m in range(0, self.config.harmonic_radial_degree + 1):
            sm = s**m
            for n in range(start_n, self.config.harmonic_order + 1):
                if n == 0:
                    cols.append(sm)
                else:
                    cols.append(sm * np.cos(n * phi))
                    cols.append(sm * np.sin(n * phi))
        return np.column_stack(cols) if cols else np.empty((s.size, 0), dtype=float)

    def predict_nominal(
        self,
        params: np.ndarray,
        r_nom_deg: np.ndarray,
        theta_nom_deg: np.ndarray,
    ) -> dict[str, np.ndarray]:
        """Predict image-space coordinates from nominal angular coordinates."""
        return evaluate_polar_distortion(
            params=params,
            radial_degree=self.config.radial_degree,
            harmonic_radial_degree=self.config.harmonic_radial_degree,
            harmonic_order=self.config.harmonic_order,
            fit_constant_terms=self.config.fit_constant_terms,
            r_nom_max_deg=self.r_nom_max_deg,
            r_nom_deg=r_nom_deg,
            theta_nom_deg=theta_nom_deg,
        )

    def predict(self, params: np.ndarray, data: GridData) -> dict[str, np.ndarray]:
        """Predict measured coordinates from nominal grid coordinates."""
        return self.predict_nominal(
            params=params,
            r_nom_deg=data.r_nom_deg,
            theta_nom_deg=data.theta_nom_deg,
        )

    def residuals(
        self,
        params: np.ndarray,
        data: GridData,
        include_field: bool = True,
    ) -> np.ndarray:
        """Compute the stacked residual vector for optimization."""
        p = np.array(params, dtype=float, copy=True)
        if not include_field:
            p[self.n_sym :] = 0.0

        pred = self.predict(p, data)
        rx = data.x - pred["x_pred"]
        ry = data.y - pred["y_pred"]
        resid = np.concatenate([rx, ry])

        if include_field and self.config.regularization > 0 and p.size > self.n_sym:
            reg = np.sqrt(self.config.regularization) * p[self.n_sym :]
            resid = np.concatenate([resid, reg])

        return resid


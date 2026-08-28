"""Polar radial/tangential distortion model definition.

The model predicts image-space coordinates from nominal polar grid coordinates
using a symmetric radial polynomial, independent radial/tangential harmonic
correction fields, and an optional axisymmetric radius-dependent angular twist.
"""

from __future__ import annotations

import numpy as np

from grid_calibration.distortion import evaluate_polar_distortion

from .config import ModelConfig
from .data import GridData
from .utils import cartesian_center_from_measured_polar, circ_median_deg


class PolarDistortionModel:
    """Symmetric radial + anisotropic harmonic distortion model."""

    def __init__(self, config: ModelConfig, r_nom_max_deg: float) -> None:
        self.config = config
        self.r_nom_max_deg = float(r_nom_max_deg)

        self.sym_names = ["cx", "cy", "theta0_deg"]
        self.sym_names += [f"k{p}" for p in range(1, config.radial_degree + 1)]

        self.dr_field_names = self._field_names(
            "dr",
            radial_degree=config.radial_harmonic_radial_degree,
            harmonic_order=config.radial_harmonic_order,
        )
        self.dtan_field_names = self._field_names(
            "dtan",
            radial_degree=config.tangential_harmonic_radial_degree,
            harmonic_order=config.tangential_harmonic_order,
        )

        twist_kind = str(config.axisymmetric_twist_kind).lower()
        if twist_kind == "none":
            self.twist_names: list[str] = []
        elif twist_kind == "tanh":
            self.twist_names = ["twist_tanh_amp_deg"]
        else:
            raise ValueError(
                "axisymmetric_twist_kind must be either 'none' or 'tanh'."
            )

        self.field_names = self.dr_field_names + self.dtan_field_names
        self.param_names = self.sym_names + self.field_names + self.twist_names
        self.n_sym = len(self.sym_names)
        self.n_dr = len(self.dr_field_names)
        self.n_dtan = len(self.dtan_field_names)
        self.n_twist = len(self.twist_names)
        self.n_total = len(self.param_names)

    def _field_names(
        self,
        axis: str,
        *,
        radial_degree: int,
        harmonic_order: int,
    ) -> list[str]:
        names: list[str] = []
        start_n = 0 if self.config.fit_constant_terms else 1
        for m in range(0, int(radial_degree) + 1):
            for n in range(start_n, int(harmonic_order) + 1):
                if n == 0:
                    names.append(f"{axis}_m{m}_c0")
                else:
                    names.append(f"{axis}_m{m}_c{n}")
                    names.append(f"{axis}_m{m}_s{n}")
        return names

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
            radial_harmonic_radial_degree=(
                self.config.radial_harmonic_radial_degree
            ),
            radial_harmonic_order=self.config.radial_harmonic_order,
            tangential_harmonic_radial_degree=(
                self.config.tangential_harmonic_radial_degree
            ),
            tangential_harmonic_order=self.config.tangential_harmonic_order,
            axisymmetric_twist_kind=self.config.axisymmetric_twist_kind,
            axisymmetric_twist_scale_deg=self.config.axisymmetric_twist_scale_deg,
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

        if include_field and self.config.regularization > 0:
            # Ridge-regularize the dense anisotropic fields. The one-parameter
            # tanh twist is deliberately left unregularized; its constrained
            # functional form is what keeps that mode identifiable/stable.
            cursor = self.n_sym
            dr_coeffs = p[cursor : cursor + self.n_dr]
            cursor += self.n_dr
            dtan_coeffs = p[cursor : cursor + self.n_dtan]
            reg_parts: list[np.ndarray] = []
            if dr_coeffs.size:
                reg_parts.append(
                    np.sqrt(self.config.regularization) * dr_coeffs
                )
            if dtan_coeffs.size:
                reg_parts.append(
                    np.sqrt(self.config.regularization) * dtan_coeffs
                )
            if reg_parts:
                resid = np.concatenate([resid, *reg_parts])

        return resid

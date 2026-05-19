from __future__ import annotations

import numpy as np

from .config import ModelConfig
from .data import GridData
from .utils import cartesian_center_from_measured_polar, circ_median_deg


class PolarDistortionModel:
    """Symmetric plus radial/tangential harmonic distortion model."""

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

    def predict(self, params: np.ndarray, data: GridData) -> dict[str, np.ndarray]:
        """Predict measured coordinates from nominal grid coordinates."""
        cx, cy, theta0_deg = params[:3]
        radial_coeffs = params[3 : self.n_sym]
        field_coeffs = params[self.n_sym :]

        u = np.deg2rad(data.r_nom_deg)
        s = data.r_nom_deg / self.r_nom_max_deg
        phi = np.deg2rad(data.theta_nom_deg + theta0_deg)

        rho_sym = np.zeros_like(u)
        for power, coeff in enumerate(radial_coeffs, start=1):
            rho_sym += coeff * u**power

        basis = self._basis(s=s, phi=phi)
        dr = np.zeros_like(rho_sym)
        dtan = np.zeros_like(rho_sym)
        if basis.size > 0:
            n_field = basis.shape[1]
            dr = basis @ field_coeffs[:n_field]
            dtan = basis @ field_coeffs[n_field:]

        rho_full = rho_sym + dr
        cos_phi = np.cos(phi)
        sin_phi = np.sin(phi)

        x_sym = cx + rho_sym * cos_phi
        y_sym = cy + rho_sym * sin_phi

        x_pred = cx + rho_full * cos_phi - dtan * sin_phi
        y_pred = cy + rho_full * sin_phi + dtan * cos_phi

        return {
            "u_rad": u,
            "s": s,
            "phi_rad": phi,
            "rho_sym": rho_sym,
            "rho_full": rho_full,
            "dr": dr,
            "dtan": dtan,
            "x_sym": x_sym,
            "y_sym": y_sym,
            "x_pred": x_pred,
            "y_pred": y_pred,
        }

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


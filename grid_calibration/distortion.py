"""Core evaluation helpers for the fitted polar distortion model.

This module intentionally has no GUI or workflow dependencies.  It contains the
plain numerical forward transform shared by the fitting code and by the public
calibration API.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def evaluate_polar_distortion(
    *,
    params: np.ndarray,
    radial_degree: int,
    harmonic_radial_degree: int,
    harmonic_order: int,
    fit_constant_terms: bool,
    r_nom_max_deg: float,
    r_nom_deg: Any,
    theta_nom_deg: Any,
) -> dict[str, np.ndarray]:
    """Evaluate the nominal-angle -> image-pixel distortion model.

    Parameters are deliberately plain numerical values so this function can be
    used without importing the Dash workflow or fit-result containers.
    ``r_nom_deg`` and ``theta_nom_deg`` are broadcast to a common shape.
    """
    r_nom, theta_nom = np.broadcast_arrays(
        np.asarray(r_nom_deg, dtype=float),
        np.asarray(theta_nom_deg, dtype=float),
    )

    if not np.isfinite(r_nom_max_deg) or r_nom_max_deg <= 0:
        raise ValueError("r_nom_max_deg must be a positive finite value.")

    params = np.asarray(params, dtype=float)
    n_sym = 3 + int(radial_degree)

    field_terms_per_axis = 0
    start_n = 0 if fit_constant_terms else 1
    for _m in range(int(harmonic_radial_degree) + 1):
        for n in range(start_n, int(harmonic_order) + 1):
            field_terms_per_axis += 1 if n == 0 else 2

    expected_params = n_sym + 2 * field_terms_per_axis
    if params.ndim != 1 or params.size != expected_params:
        raise ValueError(
            "Parameter vector has the wrong size for the model configuration: "
            f"expected {expected_params}, got {params.size}."
        )

    cx, cy, theta0_deg = params[:3]
    radial_coeffs = params[3:n_sym]
    field_coeffs = params[n_sym:]

    u = np.deg2rad(r_nom)
    s = r_nom / float(r_nom_max_deg)
    phi = np.deg2rad(theta_nom + theta0_deg)

    rho_sym = np.zeros_like(u, dtype=float)
    for power, coeff in enumerate(radial_coeffs, start=1):
        rho_sym += coeff * u**power

    basis_cols: list[np.ndarray] = []
    for m in range(int(harmonic_radial_degree) + 1):
        sm = s**m
        for n in range(start_n, int(harmonic_order) + 1):
            if n == 0:
                basis_cols.append(sm)
            else:
                basis_cols.append(sm * np.cos(n * phi))
                basis_cols.append(sm * np.sin(n * phi))

    dr = np.zeros_like(rho_sym)
    dtan = np.zeros_like(rho_sym)
    if basis_cols:
        # Keep the evaluation shape rather than flattening through column_stack.
        basis = np.stack(basis_cols, axis=-1)
        n_field = basis.shape[-1]
        dr = np.sum(basis * field_coeffs[:n_field], axis=-1)
        dtan = np.sum(basis * field_coeffs[n_field:], axis=-1)

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

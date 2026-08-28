"""Core evaluation helpers for the fitted polar distortion model.

This module intentionally has no GUI or workflow dependencies. It contains the
plain numerical forward transform shared by the fitting code and by the public
calibration API.

The current model uses separate radial and tangential harmonic bases plus an
optional axisymmetric, radius-dependent angular twist. Legacy shared-harmonic
configuration arguments remain accepted so version-1 portable calibration
artifacts can still be evaluated after loading.
"""

from __future__ import annotations

from typing import Any

import numpy as np


SUPPORTED_TWIST_KINDS = {"none", "tanh"}


def _resolve_harmonic_config(
    *,
    radial_harmonic_radial_degree: int | None,
    radial_harmonic_order: int | None,
    tangential_harmonic_radial_degree: int | None,
    tangential_harmonic_order: int | None,
    harmonic_radial_degree: int | None,
    harmonic_order: int | None,
) -> tuple[int, int, int, int]:
    """Resolve current direction-specific settings from current/legacy args."""
    if radial_harmonic_radial_degree is None:
        radial_harmonic_radial_degree = harmonic_radial_degree
    if tangential_harmonic_radial_degree is None:
        tangential_harmonic_radial_degree = harmonic_radial_degree
    if radial_harmonic_order is None:
        radial_harmonic_order = harmonic_order
    if tangential_harmonic_order is None:
        tangential_harmonic_order = harmonic_order

    values = (
        radial_harmonic_radial_degree,
        radial_harmonic_order,
        tangential_harmonic_radial_degree,
        tangential_harmonic_order,
    )
    if any(value is None for value in values):
        raise ValueError(
            "Harmonic configuration is incomplete. Supply direction-specific "
            "radial/tangential degrees and orders, or the legacy shared "
            "harmonic_radial_degree and harmonic_order values."
        )

    dr_m, dr_n, dt_m, dt_n = (int(value) for value in values)
    if min(dr_m, dr_n, dt_m, dt_n) < 0:
        raise ValueError("Harmonic degrees/orders must be non-negative.")
    return dr_m, dr_n, dt_m, dt_n


def _field_term_count(
    radial_degree: int,
    harmonic_order: int,
    *,
    fit_constant_terms: bool,
) -> int:
    """Return the number of scalar coefficients in one correction field."""
    start_n = 0 if fit_constant_terms else 1
    count = 0
    for _m in range(int(radial_degree) + 1):
        for n in range(start_n, int(harmonic_order) + 1):
            count += 1 if n == 0 else 2
    return count


def _field_basis(
    s: np.ndarray,
    phi: np.ndarray,
    *,
    radial_degree: int,
    harmonic_order: int,
    fit_constant_terms: bool,
) -> np.ndarray:
    """Build the power-radial/Fourier basis for one scalar field."""
    cols: list[np.ndarray] = []
    start_n = 0 if fit_constant_terms else 1
    for m in range(int(radial_degree) + 1):
        sm = s**m
        for n in range(start_n, int(harmonic_order) + 1):
            if n == 0:
                cols.append(sm)
            else:
                cols.append(sm * np.cos(n * phi))
                cols.append(sm * np.sin(n * phi))
    if not cols:
        return np.empty(s.shape + (0,), dtype=float)
    return np.stack(cols, axis=-1)


def _axisymmetric_twist_deg(
    *,
    kind: str,
    scale_deg: float,
    amplitude_deg: float | None,
    r_nom_deg: np.ndarray,
) -> np.ndarray:
    """Evaluate the configured radius-dependent global angular twist."""
    kind = str(kind).lower()
    if kind not in SUPPORTED_TWIST_KINDS:
        raise ValueError(
            f"Unsupported axisymmetric twist kind {kind!r}; "
            f"supported kinds are {sorted(SUPPORTED_TWIST_KINDS)}."
        )
    if kind == "none":
        return np.zeros_like(r_nom_deg, dtype=float)

    if not np.isfinite(scale_deg) or scale_deg <= 0:
        raise ValueError("axisymmetric_twist_scale_deg must be positive and finite.")
    if amplitude_deg is None or not np.isfinite(amplitude_deg):
        raise ValueError("The tanh twist model requires one finite amplitude parameter.")

    return float(amplitude_deg) * np.tanh(
        np.asarray(r_nom_deg, dtype=float) / float(scale_deg)
    )


def evaluate_polar_distortion(
    *,
    params: np.ndarray,
    radial_degree: int,
    fit_constant_terms: bool,
    r_nom_max_deg: float,
    r_nom_deg: Any,
    theta_nom_deg: Any,
    radial_harmonic_radial_degree: int | None = None,
    radial_harmonic_order: int | None = None,
    tangential_harmonic_radial_degree: int | None = None,
    tangential_harmonic_order: int | None = None,
    axisymmetric_twist_kind: str = "none",
    axisymmetric_twist_scale_deg: float = 20.0,
    # Version-1 compatibility arguments. New code should use the direction-
    # specific fields above.
    harmonic_radial_degree: int | None = None,
    harmonic_order: int | None = None,
) -> dict[str, np.ndarray]:
    """Evaluate the nominal-angle -> image-pixel distortion model.

    The current parameter ordering is::

        cx, cy, theta0_deg, k1..kR,
        <radial harmonic field coefficients>,
        <tangential harmonic field coefficients>,
        [twist_tanh_amp_deg]

    The final twist coefficient is present only when
    ``axisymmetric_twist_kind='tanh'``. The harmonic bases are evaluated using
    the untwisted global orientation ``theta_nom + theta0``; the fitted twist is
    then applied to the local radial/tangential frame used for the final pixel
    projection.

    ``r_nom_deg`` and ``theta_nom_deg`` are broadcast to a common shape.
    """
    r_nom, theta_nom = np.broadcast_arrays(
        np.asarray(r_nom_deg, dtype=float),
        np.asarray(theta_nom_deg, dtype=float),
    )

    if not np.isfinite(r_nom_max_deg) or r_nom_max_deg <= 0:
        raise ValueError("r_nom_max_deg must be a positive finite value.")
    radial_degree = int(radial_degree)
    if radial_degree < 1:
        raise ValueError("radial_degree must be at least 1.")

    dr_m, dr_n, dt_m, dt_n = _resolve_harmonic_config(
        radial_harmonic_radial_degree=radial_harmonic_radial_degree,
        radial_harmonic_order=radial_harmonic_order,
        tangential_harmonic_radial_degree=tangential_harmonic_radial_degree,
        tangential_harmonic_order=tangential_harmonic_order,
        harmonic_radial_degree=harmonic_radial_degree,
        harmonic_order=harmonic_order,
    )

    twist_kind = str(axisymmetric_twist_kind).lower()
    if twist_kind not in SUPPORTED_TWIST_KINDS:
        raise ValueError(
            f"Unsupported axisymmetric twist kind {twist_kind!r}; "
            f"supported kinds are {sorted(SUPPORTED_TWIST_KINDS)}."
        )

    params = np.asarray(params, dtype=float)
    n_sym = 3 + radial_degree
    n_dr = _field_term_count(
        dr_m, dr_n, fit_constant_terms=fit_constant_terms
    )
    n_dtan = _field_term_count(
        dt_m, dt_n, fit_constant_terms=fit_constant_terms
    )
    n_twist = 0 if twist_kind == "none" else 1
    expected_params = n_sym + n_dr + n_dtan + n_twist
    if params.ndim != 1 or params.size != expected_params:
        raise ValueError(
            "Parameter vector has the wrong size for the model configuration: "
            f"expected {expected_params}, got {params.size}."
        )

    cx, cy, theta0_deg = params[:3]
    radial_coeffs = params[3:n_sym]
    cursor = n_sym
    dr_coeffs = params[cursor : cursor + n_dr]
    cursor += n_dr
    dtan_coeffs = params[cursor : cursor + n_dtan]
    cursor += n_dtan
    twist_amp_deg = None if n_twist == 0 else float(params[cursor])

    u = np.deg2rad(r_nom)
    s = r_nom / float(r_nom_max_deg)
    phi_base = np.deg2rad(theta_nom + theta0_deg)

    rho_sym = np.zeros_like(u, dtype=float)
    for power, coeff in enumerate(radial_coeffs, start=1):
        rho_sym += coeff * u**power

    dr_basis = _field_basis(
        s,
        phi_base,
        radial_degree=dr_m,
        harmonic_order=dr_n,
        fit_constant_terms=fit_constant_terms,
    )
    dtan_basis = _field_basis(
        s,
        phi_base,
        radial_degree=dt_m,
        harmonic_order=dt_n,
        fit_constant_terms=fit_constant_terms,
    )

    dr = np.zeros_like(rho_sym)
    dtan = np.zeros_like(rho_sym)
    if dr_basis.shape[-1] > 0:
        dr = np.sum(dr_basis * dr_coeffs, axis=-1)
    if dtan_basis.shape[-1] > 0:
        dtan = np.sum(dtan_basis * dtan_coeffs, axis=-1)

    twist_deg = _axisymmetric_twist_deg(
        kind=twist_kind,
        scale_deg=float(axisymmetric_twist_scale_deg),
        amplitude_deg=twist_amp_deg,
        r_nom_deg=r_nom,
    )
    phi = phi_base + np.deg2rad(twist_deg)

    rho_full = rho_sym + dr
    cos_phi = np.cos(phi)
    sin_phi = np.sin(phi)

    # ``x_sym``/``y_sym`` use the same final local frame. During the actual
    # symmetric-only fitting stage the twist coefficient is zeroed, so these are
    # still the true symmetric predictions there.
    x_sym = cx + rho_sym * cos_phi
    y_sym = cy + rho_sym * sin_phi

    x_pred = cx + rho_full * cos_phi - dtan * sin_phi
    y_pred = cy + rho_full * sin_phi + dtan * cos_phi

    return {
        "u_rad": u,
        "s": s,
        "phi_base_rad": phi_base,
        "phi_rad": phi,
        "twist_deg": twist_deg,
        "rho_sym": rho_sym,
        "rho_full": rho_full,
        "dr": dr,
        "dtan": dtan,
        "x_sym": x_sym,
        "y_sym": y_sym,
        "x_pred": x_pred,
        "y_pred": y_pred,
    }


__all__ = ["SUPPORTED_TWIST_KINDS", "evaluate_polar_distortion"]

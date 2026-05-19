# grid_calibration/gui/steps/modeling_results/processing.py
"""
Fit a distortion model to circular-grid calibration data using radial and
 tangential harmonic corrections.

This script loads a ``.npz`` file whose ``data`` entry contains a list of
 dictionaries with at least:

- ``pixel_x`` and ``pixel_y``: measured image coordinates in pixels
- ``r`` and ``theta``: measured polar coordinates relative to an estimated grid
  center, with ``theta`` in degrees
- ``nominal_r`` and ``nominal_theta``: nominal grid coordinates in degrees

Model
-----
The fit is performed in two stages.

1. Symmetric model
   ``rho(u) = k1*u + k2*u^2 + ... + kN*u^N``
   where ``u`` is the nominal field angle in radians.

2. Full polar-harmonic model
   Adds a radial and tangential distortion field expressed in an orthogonal
   Fourier-polynomial basis:

   ``dr(s, phi)   = sum a[m,n] * s^m * cos/sin(n phi)``
   ``dtan(s, phi) = sum b[m,n] * s^m * cos/sin(n phi)``

   where ``s`` is the normalized nominal radius and ``phi`` is the nominal
   azimuth after applying the fitted global rotation offset ``theta0``.

The predicted image coordinates are then:

``x = cx + (rho + dr) * cos(phi) - dtan * sin(phi)``
``y = cy + (rho + dr) * sin(phi) + dtan * cos(phi)``

This basis is more natural than fitting separate ``dx`` and ``dy`` fields,
because it follows the radial/tangential structure seen in fisheye residuals.

Outputs
-------
The script writes:
- a multi-page PDF diagnostic report
- a compressed ``.npz`` file containing fit products
- a small JSON summary
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import matplotlib
matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from scipy.optimize import least_squares
from ....errors import ProductLoadError

logger = logging.getLogger(__name__)


def wrap_angle_deg(angle_deg: np.ndarray) -> np.ndarray:
    """Wrap angles to ``[-180, 180)`` degrees."""
    return (np.asarray(angle_deg, dtype=float) + 180.0) % 360.0 - 180.0


def robust_rms(values: np.ndarray) -> float:
    """Return the root-mean-square of an array."""
    values = np.asarray(values, dtype=float)
    return float(np.sqrt(np.mean(values**2)))


def circ_median_deg(angle_deg: np.ndarray) -> float:
    """Estimate a circular central value in degrees."""
    angle_rad = np.deg2rad(np.asarray(angle_deg, dtype=float))
    return float(np.rad2deg(np.arctan2(np.median(np.sin(angle_rad)), np.median(np.cos(angle_rad)))))


def cartesian_center_from_measured_polar(
    x: np.ndarray,
    y: np.ndarray,
    r: np.ndarray,
    theta_deg: np.ndarray,
) -> tuple[float, float]:
    """Estimate the polar origin implied by measured pixel and polar coordinates."""
    theta = np.deg2rad(theta_deg)
    cx = np.median(x - r * np.cos(theta))
    cy = np.median(y - r * np.sin(theta))
    return float(cx), float(cy)


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


def outlier_threshold_from_residual_norm(
    residual_norm: np.ndarray,
    sigma: float,
    floor_px: float,
) -> float:
    """Return an outlier threshold from the residual norm distribution."""
    residual_norm = np.asarray(residual_norm, dtype=float)
    med = float(np.median(residual_norm))
    mad = float(np.median(np.abs(residual_norm - med)))
    sigma_est = 1.4826 * mad
    return max(float(floor_px), med + float(sigma) * sigma_est)


@dataclass
class ModelConfig:
    """Configuration for the distortion model basis."""

    radial_degree: int = 4
    harmonic_radial_degree: int = 3
    harmonic_order: int = 4
    regularization: float = 1e-3
    fit_constant_terms: bool = False


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


@dataclass
class FitSummary:
    """Summary of fit quality."""

    rms: float
    median: float
    p95: float
    max_abs: float


@dataclass
class FitResult:
    """Container for optimization outputs."""

    params_sym: np.ndarray
    params_full: np.ndarray
    summary_sym: FitSummary
    summary_full: FitSummary
    pred_sym: dict[str, np.ndarray]
    pred_full: dict[str, np.ndarray]
    inlier_mask: np.ndarray
    outlier_threshold_px: float | None
    n_inliers: int
    n_outliers: int
    summary_full_inliers: FitSummary | None = None
        

def summarize_fit(data: GridData, pred: dict[str, np.ndarray]) -> tuple[FitSummary, dict[str, np.ndarray]]:
    """Compute summary diagnostics for a fit."""
    rx = data.x - pred["x_pred"]
    ry = data.y - pred["y_pred"]
    rvec = np.hypot(rx, ry)

    summary = FitSummary(
        rms=robust_rms(rvec),
        median=float(np.median(rvec)),
        p95=float(np.percentile(rvec, 95.0)),
        max_abs=float(np.max(rvec)),
    )
    details = {
        "resid_x": rx,
        "resid_y": ry,
        "resid_norm": rvec,
    }
    return summary, details


def add_center_to_prediction(pred: dict[str, np.ndarray], params: np.ndarray) -> dict[str, np.ndarray]:
    """Return a copy of the prediction dictionary augmented with center terms."""
    out = dict(pred)
    out["cx"] = np.full_like(pred["x_pred"], params[0], dtype=float)
    out["cy"] = np.full_like(pred["y_pred"], params[1], dtype=float)
    out["theta0_deg"] = np.full_like(pred["x_pred"], params[2], dtype=float)
    return out


def print_fit_report(label: str, summary: FitSummary) -> None:
    """Print a compact fit report to the terminal."""
    logger.info(f"\n[{label}]")
    logger.info(f"  RMS residual    : {summary.rms:10.4f} px")
    logger.info(f"  Median residual : {summary.median:10.4f} px")
    logger.info(f"  95th percentile : {summary.p95:10.4f} px")
    logger.info(f"  Max residual    : {summary.max_abs:10.4f} px")

def _make_synthetic_grid_data(
    r_nom_deg: np.ndarray,
    theta_nom_deg: np.ndarray,
) -> GridData:
    """
    Build a minimal :class:`GridData` object for evaluating the forward model.

    Parameters
    ----------
    r_nom_deg : :class:`numpy.ndarray`
        Nominal angular radii in degrees.
    theta_nom_deg : :class:`numpy.ndarray`
        Nominal azimuths in degrees.

    Returns
    -------
    :class:`GridData`
        Synthetic grid data with dummy measured coordinates.
    """
    r_nom_deg = np.asarray(r_nom_deg, dtype=float).ravel()
    theta_nom_deg = np.asarray(theta_nom_deg, dtype=float).ravel()
    n = r_nom_deg.size

    return GridData(
        idx=np.arange(n, dtype=int),
        x=np.zeros(n, dtype=float),
        y=np.zeros(n, dtype=float),
        r_meas=np.zeros(n, dtype=float),
        theta_meas_deg=np.zeros(n, dtype=float),
        r_nom_deg=r_nom_deg,
        theta_nom_deg=theta_nom_deg,
    )

def _plot_predicted_grid_overlay(
    ax: plt.Axes,
    model: PolarDistortionModel,
    params_full: np.ndarray,
    data: GridData,
    *,
    n_circle_samples: int = 720,
    n_spoke_samples: int = 300,
) -> None:
    """
    Overlay model-predicted circle and spoke curves in pixel space.

    Parameters
    ----------
    ax : :class:`matplotlib.axes.Axes`
        Axis where the overlay is drawn.
    model : :class:`PolarDistortionModel`
        Fitted distortion model.
    params_full : :class:`numpy.ndarray`
        Final fitted parameters.
    data : :class:`GridData`
        Calibration data used to infer which circles and spokes to draw.
    n_circle_samples, n_spoke_samples : :class:`int`, optional
        Number of samples used for drawing smooth curves.
    """
    circles = np.sort(np.unique(np.round(data.r_nom_deg / 2.5) * 2.5))
    spokes = np.sort(np.unique(np.round(data.theta_nom_deg / 2.5) * 2.5))

    theta_grid = np.linspace(0.0, 360.0, n_circle_samples, endpoint=True)
    for r0 in circles:
        synthetic = _make_synthetic_grid_data(
            r_nom_deg=np.full(theta_grid.size, r0),
            theta_nom_deg=theta_grid,
        )
        pred = model.predict(params_full, synthetic)
        ax.plot(pred["x_pred"], pred["y_pred"], "-", color="black", lw=0.55, alpha=0.45)

    r_grid = np.linspace(float(np.min(circles)), float(np.max(circles)), n_spoke_samples)
    for t0 in spokes:
        synthetic = _make_synthetic_grid_data(
            r_nom_deg=r_grid,
            theta_nom_deg=np.full(r_grid.size, t0),
        )
        pred = model.predict(params_full, synthetic)
        ax.plot(pred["x_pred"], pred["y_pred"], "-", color="black", lw=0.45, alpha=0.35)

def _plot_nominal_grid_reference(
    ax: plt.Axes,
    r_values: np.ndarray,
    theta_values: np.ndarray,
) -> None:
    """
    Draw an ideal polar grid in nominal angular Cartesian coordinates.

    Parameters
    ----------
    ax : :class:`matplotlib.axes.Axes`
        Axis where the reference grid is drawn.
    r_values : :class:`numpy.ndarray`
        Nominal circle radii in degrees.
    theta_values : :class:`numpy.ndarray`
        Nominal spoke angles in degrees.
    """
    theta = np.deg2rad(np.linspace(0.0, 360.0, 720))
    for r0 in np.sort(np.unique(r_values)):
        ax.plot(r0 * np.cos(theta), r0 * np.sin(theta), color="0.75", lw=0.5, zorder=0)

    rmax = float(np.nanmax(r_values))
    for t0 in np.deg2rad(np.sort(np.unique(theta_values))):
        ax.plot([0.0, rmax * np.cos(t0)], [0.0, rmax * np.sin(t0)], color="0.85", lw=0.35, zorder=0)

def _save_report_figure(
    fig: plt.Figure,
    pdf: PdfPages,
    figures_dir: Path | None,
    name: str,
    *,
    bbox_inches: str | None = "tight",
    dpi: int = 200,
) -> None:
    """
    Save a report figure to the multi-page PDF and optionally as a PNG.

    Parameters
    ----------
    fig : :class:`matplotlib.figure.Figure`
        Figure to save.
    pdf : :class:`matplotlib.backends.backend_pdf.PdfPages`
        Open PDF writer.
    figures_dir : :class:`pathlib.Path` or :class:`None`
        Directory where individual PNG files are written. If ``None``, only the
        PDF page is written.
    name : :class:`str`
        Base filename for the PNG output, without extension.
    bbox_inches : :class:`str` or :class:`None`, optional
        Matplotlib ``bbox_inches`` argument.
    dpi : :class:`int`, optional
        PNG resolution.
    """
    pdf.savefig(fig, bbox_inches=bbox_inches)

    if figures_dir is not None:
        figures_dir.mkdir(parents=True, exist_ok=True)
        fig.savefig(figures_dir / f"{name}.png", dpi=dpi, bbox_inches=bbox_inches)

def make_report(
    pdf_path: Path,
    data: GridData,
    pred_sym: dict[str, np.ndarray],
    pred_full: dict[str, np.ndarray],
    summary_sym: FitSummary,
    summary_full: FitSummary,
    params_full: np.ndarray,
    param_names: list[str],
    inlier_mask: np.ndarray | None = None,
    outlier_threshold_px: float | None = None,
    summary_full_inliers: FitSummary | None = None,
    model: PolarDistortionModel | None = None,
    figures_dir: Path | None = None,
) -> None:
    """
    Write a multi-page PDF report and save each diagnostic figure as a PNG.

    Parameters
    ----------
    pdf_path : :class:`pathlib.Path`
        Output PDF path.
    data : :class:`GridData`
        Calibration data.
    pred_sym, pred_full : :class:`dict`
        Prediction dictionaries for the symmetric and full models.
    summary_sym, summary_full : :class:`FitSummary`
        Fit summaries.
    params_full : :class:`numpy.ndarray`
        Final fitted parameters.
    param_names : :class:`list` [:class:`str`]
        Names of the fitted parameters.
    inlier_mask : :class:`numpy.ndarray` or :class:`None`, optional
        Boolean mask for points used in the final outlier-refit.
    outlier_threshold_px : :class:`float` or :class:`None`, optional
        Residual-norm threshold used for outlier rejection.
    summary_full_inliers : :class:`FitSummary` or :class:`None`, optional
        Final fit summary evaluated on inliers only.
    model : :class:`PolarDistortionModel` or :class:`None`, optional
        Fitted model instance. If provided, extra geometric model overlays are
        added to the report.
    figures_dir : :class:`pathlib.Path` or :class:`None`, optional
        Directory where individual PNG figures are written. If ``None``, a
        directory named ``<pdf_stem>_figures`` is created next to the PDF.
    """
    if figures_dir is None:
        figures_dir = pdf_path.parent / f"{pdf_path.stem}_figures"

    rx_sym = data.x - pred_sym["x_pred"]
    ry_sym = data.y - pred_sym["y_pred"]
    rn_sym = np.hypot(rx_sym, ry_sym)

    rx = data.x - pred_full["x_pred"]
    ry = data.y - pred_full["y_pred"]
    rn = np.hypot(rx, ry)

    has_outliers = inlier_mask is not None and outlier_threshold_px is not None
    if has_outliers:
        inlier_mask = np.asarray(inlier_mask, dtype=bool)
        outlier_mask = ~inlier_mask
    else:
        inlier_mask = np.ones(data.x.size, dtype=bool)
        outlier_mask = np.zeros(data.x.size, dtype=bool)

    phi_nom = np.deg2rad(data.theta_nom_deg + params_full[2])
    ux = np.cos(phi_nom)
    uy = np.sin(phi_nom)
    tx = -uy
    ty = ux

    resid_radial = rx * ux + ry * uy
    resid_tangential = rx * tx + ry * ty

    measured_r_from_center = np.hypot(data.x - params_full[0], data.y - params_full[1])
    measured_theta_from_center_deg = np.rad2deg(np.arctan2(data.y - params_full[1], data.x - params_full[0]))
    theta_resid_deg = wrap_angle_deg(measured_theta_from_center_deg - (data.theta_nom_deg + params_full[2]))

    distortion_mag = np.hypot(pred_full["dr"], pred_full["dtan"])
    correction_x = pred_full["dr"] * ux - pred_full["dtan"] * uy
    correction_y = pred_full["dr"] * uy + pred_full["dtan"] * ux

    with PdfPages(pdf_path) as pdf:
        fig, ax = plt.subplots(figsize=(11, 8.5))
        ax.axis("off")
        n_inliers = int(np.sum(inlier_mask)) if inlier_mask is not None else data.x.size
        n_outliers = data.x.size - n_inliers
        lines = [
            "Grid distortion fit report",
            "",
            f"N points: {data.x.size}",
            f"Estimated distortion center: ({params_full[0]:.3f}, {params_full[1]:.3f}) px",
            f"Global rotation offset theta0: {params_full[2]:.6f} deg",
            "",
            "Symmetric-only fit:",
            f" RMS={summary_sym.rms:.4f} px, median={summary_sym.median:.4f} px, p95={summary_sym.p95:.4f} px, max={summary_sym.max_abs:.4f} px",
            "",
            "Full polar-harmonic fit (all points):",
            f" RMS={summary_full.rms:.4f} px, median={summary_full.median:.4f} px, p95={summary_full.p95:.4f} px, max={summary_full.max_abs:.4f} px",
        ]
        if inlier_mask is not None and outlier_threshold_px is not None:
            lines += [
                "",
                f"Outlier rejection threshold: {outlier_threshold_px:.4f} px",
                f"Inliers used for final refit: {n_inliers}",
                f"Rejected outliers: {n_outliers}",
            ]
            if summary_full_inliers is not None:
                lines += [
                    "Full polar-harmonic fit (inliers only):",
                    f" RMS={summary_full_inliers.rms:.4f} px, median={summary_full_inliers.median:.4f} px, p95={summary_full_inliers.p95:.4f} px, max={summary_full_inliers.max_abs:.4f} px",
                ]
        lines += ["", "Top parameters by absolute value:"]
        order = np.argsort(np.abs(params_full))[::-1]
        for idx in order[:18]:
            lines.append(f"  {param_names[idx]:<16s} = {params_full[idx]: .6e}")
        ax.text(0.03, 0.97, "\n".join(lines), va="top", ha="left", family="monospace", fontsize=11)
        _save_report_figure(fig, pdf, figures_dir, "01_summary")
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(8, 8))
        sc = ax.scatter(data.x, data.y, c=rn, s=8)
        if np.any(outlier_mask):
            ax.scatter(data.x[outlier_mask], data.y[outlier_mask], facecolors="none", edgecolors="red", s=28, linewidths=0.8)
        ax.set_title("Measured grid points colored by final residual norm")
        ax.set_xlabel("pixel_x")
        ax.set_ylabel("pixel_y")
        ax.set_aspect("equal")
        ax.scatter([params_full[0]], [params_full[1]], marker="x", s=120)
        fig.colorbar(sc, ax=ax, label="Residual norm [px]")
        _save_report_figure(fig, pdf, figures_dir, "02_residual_map_pixel_space")
        plt.close(fig)

        fig, axes = plt.subplots(1, 2, figsize=(13, 5))
        vmax = max(np.percentile(rn_sym, 99), np.percentile(rn, 99))
        axes[0].scatter(data.theta_nom_deg, data.r_nom_deg, c=rn_sym, s=8, vmin=0, vmax=vmax)
        axes[0].set_title("Symmetric-only residuals")
        axes[0].set_xlabel("Nominal theta [deg]")
        axes[0].set_ylabel("Nominal r [deg]")
        s2 = axes[1].scatter(data.theta_nom_deg, data.r_nom_deg, c=rn, s=8, vmin=0, vmax=vmax)
        axes[1].set_title("Full-model residuals")
        axes[1].set_xlabel("Nominal theta [deg]")
        axes[1].set_ylabel("Nominal r [deg]")
        fig.colorbar(s2, ax=axes, label="Residual norm [px]")
        _save_report_figure(fig, pdf, figures_dir, "03_residuals_nominal_space")
        plt.close(fig)

        qstride = max(1, data.x.size // 800)
        fig, axes = plt.subplots(1, 2, figsize=(13, 5))
        axes[0].quiver(
            data.x[::qstride], data.y[::qstride], rx_sym[::qstride], ry_sym[::qstride],
            angles="xy", scale_units="xy", scale=1,
        )
        axes[0].set_title("Residual field after symmetric fit")
        axes[0].set_xlabel("pixel_x")
        axes[0].set_ylabel("pixel_y")
        axes[0].set_aspect("equal")
        axes[1].quiver(
            data.x[::qstride], data.y[::qstride], rx[::qstride], ry[::qstride],
            angles="xy", scale_units="xy", scale=1,
        )
        axes[1].set_title("Residual field after full fit")
        axes[1].set_xlabel("pixel_x")
        axes[1].set_ylabel("pixel_y")
        axes[1].set_aspect("equal")
        _save_report_figure(fig, pdf, figures_dir, "04_residual_vector_fields")
        plt.close(fig)

        fig, axes = plt.subplots(2, 2, figsize=(13, 10))
        sc = axes[0, 0].scatter(data.theta_nom_deg, data.r_nom_deg, c=resid_radial, s=8)
        axes[0, 0].set_title("Radial residual component")
        axes[0, 0].set_xlabel("Nominal theta [deg]")
        axes[0, 0].set_ylabel("Nominal r [deg]")
        fig.colorbar(sc, ax=axes[0, 0], label="px")

        sc = axes[0, 1].scatter(data.theta_nom_deg, data.r_nom_deg, c=resid_tangential, s=8)
        axes[0, 1].set_title("Tangential residual component")
        axes[0, 1].set_xlabel("Nominal theta [deg]")
        axes[0, 1].set_ylabel("Nominal r [deg]")
        fig.colorbar(sc, ax=axes[0, 1], label="px")

        sc = axes[1, 0].scatter(data.theta_nom_deg, data.r_nom_deg, c=pred_full["dr"], s=8)
        axes[1, 0].set_title("Fitted radial correction dr")
        axes[1, 0].set_xlabel("Nominal theta [deg]")
        axes[1, 0].set_ylabel("Nominal r [deg]")
        fig.colorbar(sc, ax=axes[1, 0], label="px")

        sc = axes[1, 1].scatter(data.theta_nom_deg, data.r_nom_deg, c=pred_full["dtan"], s=8)
        axes[1, 1].set_title("Fitted tangential correction dtan")
        axes[1, 1].set_xlabel("Nominal theta [deg]")
        axes[1, 1].set_ylabel("Nominal r [deg]")
        fig.colorbar(sc, ax=axes[1, 1], label="px")
        _save_report_figure(fig, pdf, figures_dir, "05_radial_tangential_components")
        plt.close(fig)

        fig, axes = plt.subplots(2, 2, figsize=(13, 10))
        sc = axes[0, 0].scatter(data.r_nom_deg, measured_r_from_center - pred_full["rho_sym"], c=data.theta_nom_deg, s=8)
        axes[0, 0].set_title("Measured radius minus symmetric radius")
        axes[0, 0].set_xlabel("Nominal r [deg]")
        axes[0, 0].set_ylabel("Delta radius [px]")
        fig.colorbar(sc, ax=axes[0, 0], label="Nominal theta [deg]")

        sc = axes[0, 1].scatter(data.r_nom_deg, theta_resid_deg, c=data.theta_nom_deg, s=8)
        axes[0, 1].set_title("Angular residual about fitted center")
        axes[0, 1].set_xlabel("Nominal r [deg]")
        axes[0, 1].set_ylabel("Delta theta [deg]")
        fig.colorbar(sc, ax=axes[0, 1], label="Nominal theta [deg]")

        sc = axes[1, 0].scatter(data.r_nom_deg, resid_radial, c=data.theta_nom_deg, s=8)
        axes[1, 0].scatter(
            data.r_nom_deg[outlier_mask],
            resid_radial[outlier_mask],
            facecolors="none",
            edgecolors="red",
            s=36,
            linewidths=0.9,
        )
        if has_outliers:
            axes[1, 0].axhline(outlier_threshold_px, color="red", ls="--", lw=1)
            axes[1, 0].axhline(-outlier_threshold_px, color="red", ls="--", lw=1)
        axes[1, 0].set_title("Radial residual vs nominal r (red = rejected)")
        axes[1, 0].set_xlabel("Nominal r [deg]")
        axes[1, 0].set_ylabel("Radial residual [px]")
        fig.colorbar(sc, ax=axes[1, 0], label="Nominal theta [deg]")

        sc = axes[1, 1].scatter(data.r_nom_deg, resid_tangential, c=data.theta_nom_deg, s=8)
        axes[1, 1].scatter(
            data.r_nom_deg[outlier_mask],
            resid_tangential[outlier_mask],
            facecolors="none",
            edgecolors="red",
            s=36,
            linewidths=0.9,
        )
        if has_outliers:
            axes[1, 1].axhline(outlier_threshold_px, color="red", ls="--", lw=1)
            axes[1, 1].axhline(-outlier_threshold_px, color="red", ls="--", lw=1)
        axes[1, 1].set_title("Tangential residual vs nominal r (red = rejected)")
        axes[1, 1].set_xlabel("Nominal r [deg]")
        axes[1, 1].set_ylabel("Tangential residual [px]")
        fig.colorbar(sc, ax=axes[1, 1], label="Nominal theta [deg]")
        _save_report_figure(fig, pdf, figures_dir, "06_residuals_vs_radius")
        plt.close(fig)

        fig, axes = plt.subplots(1, 3, figsize=(15, 4.8))
        axes[0].hist(rn_sym, bins=60)
        axes[0].set_title("Symmetric-only residual norm")
        axes[0].set_xlabel("px")
        axes[0].set_ylabel("Count")

        axes[1].hist(rn, bins=60)
        if has_outliers:
            axes[1].axvline(outlier_threshold_px, color="red", ls="--", lw=1.5)
        axes[1].set_title("Full-model residual norm")
        axes[1].set_xlabel("px")
        axes[1].set_ylabel("Count")

        axes[2].hist(rn_sym - rn, bins=60)
        axes[2].set_title("Improvement in residual norm")
        axes[2].set_xlabel("(sym - full) [px]")
        axes[2].set_ylabel("Count")
        _save_report_figure(fig, pdf, figures_dir, "07_residual_histograms")
        plt.close(fig)

        fig, axes = plt.subplots(2, 2, figsize=(13, 10))
        sc = axes[0, 0].scatter(data.theta_nom_deg, rx, c=data.r_nom_deg, s=8)
        axes[0, 0].set_title("Residual x vs nominal theta")
        axes[0, 0].set_xlabel("Nominal theta [deg]")
        axes[0, 0].set_ylabel("Residual x [px]")
        fig.colorbar(sc, ax=axes[0, 0], label="Nominal r [deg]")

        sc = axes[0, 1].scatter(data.theta_nom_deg, ry, c=data.r_nom_deg, s=8)
        axes[0, 1].set_title("Residual y vs nominal theta")
        axes[0, 1].set_xlabel("Nominal theta [deg]")
        axes[0, 1].set_ylabel("Residual y [px]")
        fig.colorbar(sc, ax=axes[0, 1], label="Nominal r [deg]")

        sc = axes[1, 0].scatter(data.theta_nom_deg, resid_radial, c=data.r_nom_deg, s=8)
        axes[1, 0].set_title("Radial residual vs nominal theta")
        axes[1, 0].set_xlabel("Nominal theta [deg]")
        axes[1, 0].set_ylabel("Radial residual [px]")
        fig.colorbar(sc, ax=axes[1, 0], label="Nominal r [deg]")

        sc = axes[1, 1].scatter(data.theta_nom_deg, resid_tangential, c=data.r_nom_deg, s=8)
        axes[1, 1].set_title("Tangential residual vs nominal theta")
        axes[1, 1].set_xlabel("Nominal theta [deg]")
        axes[1, 1].set_ylabel("Tangential residual [px]")
        fig.colorbar(sc, ax=axes[1, 1], label="Nominal r [deg]")
        _save_report_figure(fig, pdf, figures_dir, "08_residuals_vs_theta")
        plt.close(fig)

        fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
        sc = axes[0].scatter(data.x, data.y, c=distortion_mag, s=8)
        axes[0].scatter([params_full[0]], [params_full[1]], marker="x", s=120, color="red")
        axes[0].set_title("Fitted distortion-correction magnitude")
        axes[0].set_xlabel("pixel_x")
        axes[0].set_ylabel("pixel_y")
        axes[0].set_aspect("equal")
        fig.colorbar(sc, ax=axes[0], label=r"$\sqrt{dr^2 + dtan^2}$ [px]")

        qstride_corr = max(1, data.x.size // 700)
        axes[1].quiver(
            data.x[::qstride_corr],
            data.y[::qstride_corr],
            correction_x[::qstride_corr],
            correction_y[::qstride_corr],
            angles="xy",
            scale_units="xy",
            scale=1,
        )
        axes[1].scatter([params_full[0]], [params_full[1]], marker="x", s=120, color="red")
        axes[1].set_title("Fitted harmonic correction vectors")
        axes[1].set_xlabel("pixel_x")
        axes[1].set_ylabel("pixel_y")
        axes[1].set_aspect("equal")
        _save_report_figure(fig, pdf, figures_dir, "09_distortion_magnitude_pixel_space")
        plt.close(fig)

        if model is not None:
            fig, ax = plt.subplots(figsize=(9, 9))
            ax.scatter(data.x, data.y, s=5, color="tab:orange", alpha=0.45, label="measured grid points")
            _plot_predicted_grid_overlay(ax, model, params_full, data)
            if np.any(outlier_mask):
                ax.scatter(
                    data.x[outlier_mask],
                    data.y[outlier_mask],
                    facecolors="none",
                    edgecolors="red",
                    s=32,
                    linewidths=0.9,
                    label="rejected outliers",
                )
            ax.scatter([params_full[0]], [params_full[1]], marker="x", s=120, color="red", label="distortion center")
            ax.set_title("Model-predicted grid overlay in pixel space")
            ax.set_xlabel("pixel_x")
            ax.set_ylabel("pixel_y")
            ax.set_aspect("equal")
            ax.legend(loc="best", fontsize=8)
            _save_report_figure(fig, pdf, figures_dir, "10_predicted_grid_overlay_pixel_space")
            plt.close(fig)

        theta_nom_rad = np.deg2rad(data.theta_nom_deg)
        xu = data.r_nom_deg * np.cos(theta_nom_rad)
        yu = data.r_nom_deg * np.sin(theta_nom_rad)

        fig, ax = plt.subplots(figsize=(8, 8))
        _plot_nominal_grid_reference(
            ax,
            r_values=np.round(data.r_nom_deg / 2.5) * 2.5,
            theta_values=np.round(data.theta_nom_deg / 2.5) * 2.5,
        )
        sc = ax.scatter(xu, yu, c=rn, s=8, zorder=2)
        if np.any(outlier_mask):
            ax.scatter(xu[outlier_mask], yu[outlier_mask], facecolors="none", edgecolors="red", s=30, linewidths=0.9, zorder=3)
        ax.set_title("Undistorted nominal-grid check")
        ax.set_xlabel(r"$r_{\rm nom}\cos\theta_{\rm nom}$ [deg]")
        ax.set_ylabel(r"$r_{\rm nom}\sin\theta_{\rm nom}$ [deg]")
        ax.set_aspect("equal")
        fig.colorbar(sc, ax=ax, label="Residual norm [px]")
        _save_report_figure(fig, pdf, figures_dir, "11_undistorted_nominal_grid_check")
        plt.close(fig)


def fit_model(
    data: GridData,
    config: ModelConfig,
    max_nfev: int,
    outlier_rejection_sigma: float | None = None,
    outlier_rejection_floor_px: float = 2.5,
    min_inlier_fraction: float = 0.90,
) -> tuple[FitResult, PolarDistortionModel]:
    """Fit the symmetric and full distortion models."""
    model = PolarDistortionModel(config=config, r_nom_max_deg=float(np.max(data.r_nom_deg)))
    p0 = model.initial_parameters(data)

    logger.info("Initial guess:")
    logger.info(f"  cx     = {p0[0]:.4f} px")
    logger.info(f"  cy     = {p0[1]:.4f} px")
    logger.info(f"  theta0 = {p0[2]:.6f} deg")
    for i, name in enumerate(model.sym_names[3:], start=3):
        logger.info(f"  {name:<6s} = {p0[i]:.6e}")

    logger.info("\nStage 1: fitting symmetric near-equidistant model...")
    res_sym = least_squares(
        fun=lambda p: model.residuals(p, data, include_field=False),
        x0=p0,
        loss="soft_l1",
        f_scale=2.0,
        max_nfev=max_nfev,
        verbose=2 if logger.isEnabledFor(logging.DEBUG) else 0,
    )
    p_sym = np.array(res_sym.x, copy=True)
    p_sym[model.n_sym :] = 0.0
    pred_sym = add_center_to_prediction(model.predict(p_sym, data), p_sym)
    summary_sym, _ = summarize_fit(data, pred_sym)
    print_fit_report("symmetric model", summary_sym)

    logger.info("\nStage 2: fitting polar radial/tangential harmonic correction...")
    res_full = least_squares(
        fun=lambda p: model.residuals(p, data, include_field=True),
        x0=p_sym,
        loss="soft_l1",
        f_scale=2.0,
        max_nfev=max_nfev,
        verbose=2 if logger.isEnabledFor(logging.DEBUG) else 0,
    )
    p_full = np.array(res_full.x, copy=True)
    pred_full = add_center_to_prediction(model.predict(p_full, data), p_full)
    summary_full_all, details_full = summarize_fit(data, pred_full)
    print_fit_report("full model (all points)", summary_full_all)

    inlier_mask = np.ones(data.x.size, dtype=bool)
    outlier_threshold_px: float | None = None
    summary_full_inliers: FitSummary | None = None

    if outlier_rejection_sigma is not None and outlier_rejection_sigma > 0:
        outlier_threshold_px = outlier_threshold_from_residual_norm(
            residual_norm=details_full["resid_norm"],
            sigma=outlier_rejection_sigma,
            floor_px=outlier_rejection_floor_px,
        )
        inlier_mask = details_full["resid_norm"] <= outlier_threshold_px
        min_inliers = max(1, int(np.ceil(min_inlier_fraction * data.x.size)))

        logger.info("\nOutlier rejection pass:")
        logger.info(f"  threshold       : {outlier_threshold_px:.4f} px")
        logger.info(f"  inliers kept    : {int(np.sum(inlier_mask))} / {data.x.size}")
        logger.info(f"  outliers removed: {int(np.sum(~inlier_mask))}")

        if np.sum(inlier_mask) >= min_inliers and np.any(~inlier_mask):
            data_inliers = data.subset(inlier_mask)
            logger.info("\nStage 3: refitting full model on inliers only...")
            res_refit = least_squares(
                fun=lambda p: model.residuals(p, data_inliers, include_field=True),
                x0=p_full,
                loss="soft_l1",
                f_scale=2.0,
                max_nfev=max_nfev,
                verbose=2 if logger.isEnabledFor(logging.DEBUG) else 0,
            )
            p_full = np.array(res_refit.x, copy=True)
            pred_full = add_center_to_prediction(model.predict(p_full, data), p_full)
            summary_full_all, _ = summarize_fit(data, pred_full)

            pred_full_in = add_center_to_prediction(model.predict(p_full, data_inliers), p_full)
            summary_full_inliers, _ = summarize_fit(data_inliers, pred_full_in)
            print_fit_report("final full model (all points)", summary_full_all)
            print_fit_report("final full model (inliers only)", summary_full_inliers)
        else:
            logger.info("  skipping outlier-refit because too few outliers were found or too many points would be removed.")

    improvement = summary_sym.rms - summary_full_all.rms
    frac = 100.0 * improvement / summary_sym.rms if summary_sym.rms > 0 else 0.0
    logger.info(f"\nRMS improvement: {improvement:.4f} px ({frac:.2f}%)")

    logger.info("\nFinal fitted parameters:")
    for name, value in zip(model.param_names, p_full, strict=True):
        logger.info(f"  {name:<16s} = {value: .8e}")

    result = FitResult(
        params_sym=p_sym,
        params_full=p_full,
        summary_sym=summary_sym,
        summary_full=summary_full_all,
        pred_sym=pred_sym,
        pred_full=pred_full,
        inlier_mask=inlier_mask,
        outlier_threshold_px=outlier_threshold_px,
        n_inliers=int(np.sum(inlier_mask)),
        n_outliers=int(np.sum(~inlier_mask)),
        summary_full_inliers=summary_full_inliers,
    )
    return result, model


def model_nominal_grid(raw_assignment, params):
    """
    Fit the distortion model from raw nominal-assignment records.
    """
    logger.info("Loading data...")

    data = GridData.from_records(raw_assignment)

    logger.info(f"Loaded {data.x.size} valid points.")  

    config = ModelConfig(
        radial_degree=params["radial-degree"],
        harmonic_radial_degree=params["harmonic-radial-degree"],
        harmonic_order=params["harmonic-order"],
        regularization=params["regularization"],
        fit_constant_terms=params["fit-constant-terms"],
    )

    result, model = fit_model(
        data=data,
        config=config,
        max_nfev=params["max-nfev"],
        outlier_rejection_sigma=params["outlier-rejection-sigma"],
        outlier_rejection_floor_px=params["outlier-rejection-floor-px"],
        min_inlier_fraction=params["min-inlier-fraction"],
    )

    return result, model, data
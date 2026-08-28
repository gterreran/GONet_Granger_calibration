"""
Matplotlib/PDF diagnostic report generation for fitted distortion models.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg", force=True)

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from numpy.polynomial.chebyshev import chebfit, chebval

from grid_calibration.calibration import GridCalibration

from .data import GridData
from .model import PolarDistortionModel
from .results import FitSummary
from .utils import wrap_angle_deg


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



def _robust_sigma_arcmin(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return float("nan")
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    sigma = 1.482602218505602 * mad
    if not np.isfinite(sigma) or sigma <= 0.0:
        sigma = float(np.std(values))
    return sigma


def _wrap_degrees(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    return (values + 180.0) % 360.0 - 180.0


def _signed_cross_spoke_arcmin(
    recovered_r_deg: np.ndarray,
    recovered_theta_deg: np.ndarray,
    spoke_theta_deg: float | np.ndarray,
) -> np.ndarray:
    r_rad = np.deg2rad(np.asarray(recovered_r_deg, dtype=float))
    delta_theta_rad = np.deg2rad(
        _wrap_degrees(
            np.asarray(recovered_theta_deg, dtype=float)
            - np.asarray(spoke_theta_deg, dtype=float)
        )
    )
    argument = np.sin(r_rad) * np.sin(delta_theta_rad)
    return np.rad2deg(np.arcsin(np.clip(argument, -1.0, 1.0))) * 60.0


def _fitted_spoke_theta_deg(
    recovered_r_deg: np.ndarray,
    recovered_theta_deg: np.ndarray,
) -> float:
    r_rad = np.deg2rad(np.asarray(recovered_r_deg, dtype=float))
    theta_rad = np.deg2rad(np.asarray(recovered_theta_deg, dtype=float))
    weights = np.sin(r_rad) ** 2
    x = float(np.sum(weights * np.cos(theta_rad)))
    y = float(np.sum(weights * np.sin(theta_rad)))
    if abs(x) < 1e-15 and abs(y) < 1e-15:
        return float(
            np.mod(
                np.rad2deg(np.angle(np.mean(np.exp(1j * theta_rad)))),
                360.0,
            )
        )
    return float(np.mod(np.rad2deg(np.arctan2(y, x)), 360.0))


def _smooth_spoke_ptp(
    r_deg: np.ndarray,
    residual_arcmin: np.ndarray,
    degree: int = 3,
) -> float:
    r = np.asarray(r_deg, dtype=float)
    y = np.asarray(residual_arcmin, dtype=float)
    if r.size <= degree:
        return float("nan")
    rmin = float(np.min(r))
    rmax = float(np.max(r))
    if rmax <= rmin:
        return 0.0
    z = 2.0 * (r - rmin) / (rmax - rmin) - 1.0
    coeff = chebfit(z, y, deg=degree)
    smooth = chebval(np.linspace(-1.0, 1.0, 256), coeff)
    return float(np.ptp(smooth))


def _smooth_ring_ptp(
    theta_deg: np.ndarray,
    residual_arcmin: np.ndarray,
    order: int = 6,
) -> float:
    theta = np.deg2rad(np.asarray(theta_deg, dtype=float))
    y = np.asarray(residual_arcmin, dtype=float)
    if theta.size < 3:
        return float("nan")
    if theta.size < 2 * order + 1:
        order = max(1, (theta.size - 1) // 2)
    cols = [np.ones_like(theta)]
    for n in range(1, order + 1):
        cols.extend([np.cos(n * theta), np.sin(n * theta)])
    coeff, *_ = np.linalg.lstsq(np.column_stack(cols), y, rcond=None)

    grid = np.linspace(0.0, 2.0 * np.pi, 720, endpoint=False)
    grid_cols = [np.ones_like(grid)]
    for n in range(1, order + 1):
        grid_cols.extend([np.cos(n * grid), np.sin(n * grid)])
    smooth = np.column_stack(grid_cols) @ coeff
    return float(np.ptp(smooth))


def _inverse_angular_diagnostics(
    calibration: GridCalibration,
    data: GridData,
    *,
    max_r_deg: float,
    ring_r_min_deg: float = 20.0,
    min_points_per_group: int = 5,
) -> dict[str, object]:
    """Calculate the ring/spoke inverse diagnostics used in model selection."""
    max_r = min(
        float(max_r_deg),
        float(calibration.calibrated_angular_range_deg[1]),
    )
    analysis = np.asarray(data.r_nom_deg <= max_r, dtype=bool)
    r_rec, theta_rec = calibration.pixel_to_angle(
        data.x[analysis], data.y[analysis], strict=False
    )
    r_rec = np.asarray(r_rec, dtype=float)
    theta_rec = np.asarray(theta_rec, dtype=float)
    r_nom = np.asarray(data.r_nom_deg[analysis], dtype=float)
    theta_nom = np.asarray(data.theta_nom_deg[analysis], dtype=float)

    valid = np.isfinite(r_rec) & np.isfinite(theta_rec)
    r_rec = r_rec[valid]
    theta_rec = theta_rec[valid]
    r_nom = r_nom[valid]
    theta_nom = theta_nom[valid]

    radial_arcmin = (r_rec - r_nom) * 60.0
    cross_arcmin = _signed_cross_spoke_arcmin(r_rec, theta_rec, theta_nom)

    ring_rows: list[dict[str, float]] = []
    for ring_r in np.unique(r_nom):
        if ring_r < ring_r_min_deg:
            continue
        mask = np.isclose(r_nom, ring_r, atol=1e-9, rtol=0)
        if np.count_nonzero(mask) < min_points_per_group:
            continue
        rr = r_rec[mask]
        residual = (rr - np.median(rr)) * 60.0
        ring_rows.append(
            {
                "nominal_r_deg": float(ring_r),
                "sigma_arcmin": _robust_sigma_arcmin(residual),
                "ptp_arcmin": float(np.ptp(residual)),
                "smooth_ptp_arcmin": _smooth_ring_ptp(theta_nom[mask], residual),
                "median_bias_arcmin": float(np.median((rr - ring_r) * 60.0)),
            }
        )

    spoke_rows: list[dict[str, float]] = []
    spoke_curves: list[dict[str, object]] = []
    for theta0 in np.unique(theta_nom):
        mask = np.isclose(theta_nom, theta0, atol=1e-9, rtol=0)
        if np.count_nonzero(mask) < min_points_per_group:
            continue
        order = np.argsort(r_nom[mask])
        rn = r_nom[mask][order]
        rr = r_rec[mask][order]
        tr = theta_rec[mask][order]
        fitted_theta = _fitted_spoke_theta_deg(rr, tr)
        fitted_cross = _signed_cross_spoke_arcmin(rr, tr, fitted_theta)
        row = {
            "nominal_theta_deg": float(theta0),
            "theta_offset_arcmin": float(
                _wrap_degrees(np.asarray([fitted_theta - theta0]))[0] * 60.0
            ),
            "sigma_arcmin": _robust_sigma_arcmin(fitted_cross),
            "ptp_arcmin": float(np.ptp(fitted_cross)),
            "smooth_ptp_arcmin": _smooth_spoke_ptp(rn, fitted_cross),
        }
        spoke_rows.append(row)
        spoke_curves.append(
            {
                **row,
                "r_nom_deg": rn,
                "fitted_cross_arcmin": fitted_cross,
            }
        )

    return {
        "max_r_deg": max_r,
        "r_nom_deg": r_nom,
        "theta_nom_deg": theta_nom,
        "radial_arcmin": radial_arcmin,
        "cross_arcmin": cross_arcmin,
        "ring_rows": ring_rows,
        "spoke_rows": spoke_rows,
        "spoke_curves": spoke_curves,
    }

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
    calibration: GridCalibration | None = None,
    inverse_validation_max_r_deg: float = 70.0,
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
    calibration : :class:`grid_calibration.calibration.GridCalibration` or :class:`None`, optional
        Public portable calibration evaluator. When supplied, inverse angular
        ring/spoke validation pages are appended to the report.
    inverse_validation_max_r_deg : :class:`float`, optional
        Maximum nominal radius used for inverse angular validation.
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

    # Decompose residuals in the final local radial/tangential frame. For the
    # selected model this includes the fitted axisymmetric twist.
    phi_nom = np.asarray(
        pred_full.get(
            "phi_rad", np.deg2rad(data.theta_nom_deg + params_full[2])
        ),
        dtype=float,
    )
    ux = np.cos(phi_nom)
    uy = np.sin(phi_nom)
    tx = -uy
    ty = ux

    resid_radial = rx * ux + ry * uy
    resid_tangential = rx * tx + ry * ty

    measured_r_from_center = np.hypot(data.x - params_full[0], data.y - params_full[1])
    measured_theta_from_center_deg = np.rad2deg(np.arctan2(data.y - params_full[1], data.x - params_full[0]))
    theta_resid_deg = wrap_angle_deg(
        measured_theta_from_center_deg - np.rad2deg(phi_nom)
    )

    distortion_mag = np.hypot(pred_full["dr"], pred_full["dtan"])
    correction_x = pred_full["dr"] * ux - pred_full["dtan"] * uy
    correction_y = pred_full["dr"] * uy + pred_full["dtan"] * ux

    inverse_details = None
    if calibration is not None:
        inverse_details = _inverse_angular_diagnostics(
            calibration,
            data,
            max_r_deg=float(inverse_validation_max_r_deg),
        )

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
        if calibration is not None:
            q = calibration.fit_quality
            lines += [
                "",
                "Model configuration:",
                f" radial degree={calibration.radial_degree}",
                f" dr field: M={calibration.radial_harmonic_radial_degree}, N={calibration.radial_harmonic_order}",
                f" dtan field: M={calibration.tangential_harmonic_radial_degree}, N={calibration.tangential_harmonic_order}",
                f" axisymmetric twist={calibration.axisymmetric_twist_kind}, scale={calibration.axisymmetric_twist_scale_deg:.2f} deg",
            ]
            if q.inverse_validation_max_r_deg is not None:
                lines += [
                    "",
                    f"Inverse angular validation (r <= {q.inverse_validation_max_r_deg:.1f} deg):",
                    f" radial robust sigma={q.inverse_radial_robust_sigma_arcmin:.3f} arcmin, p95 abs={q.inverse_radial_p95_abs_arcmin:.3f} arcmin",
                    f" cross-spoke robust sigma={q.inverse_cross_robust_sigma_arcmin:.3f} arcmin, p95 abs={q.inverse_cross_p95_abs_arcmin:.3f} arcmin",
                ]
                if inverse_details is not None:
                    ring_smooth = np.asarray(
                        [row["smooth_ptp_arcmin"] for row in inverse_details["ring_rows"]],
                        dtype=float,
                    )
                    spoke_smooth = np.asarray(
                        [row["smooth_ptp_arcmin"] for row in inverse_details["spoke_rows"]],
                        dtype=float,
                    )
                    if ring_smooth.size:
                        lines.append(
                            f" ring coherent smooth P90={np.nanpercentile(ring_smooth, 90):.3f} arcmin"
                        )
                    if spoke_smooth.size:
                        lines.append(
                            f" spoke coherent smooth P90={np.nanpercentile(spoke_smooth, 90):.3f} arcmin"
                        )
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

        if inverse_details is not None:
            r_nom_inv = np.asarray(inverse_details["r_nom_deg"], dtype=float)
            theta_nom_inv = np.asarray(inverse_details["theta_nom_deg"], dtype=float)
            radial_arcmin = np.asarray(inverse_details["radial_arcmin"], dtype=float)
            cross_arcmin = np.asarray(inverse_details["cross_arcmin"], dtype=float)
            max_r_inv = float(inverse_details["max_r_deg"])

            fig, axes = plt.subplots(2, 1, figsize=(11, 9), sharex=True)
            sc0 = axes[0].scatter(
                r_nom_inv, cross_arcmin, c=theta_nom_inv, s=9, alpha=0.72
            )
            axes[0].axhline(0.0, ls="--", lw=1, alpha=0.6)
            axes[0].set_ylabel("cross-spoke residual [arcmin]")
            axes[0].set_title(
                f"Inverse angular residual field (nominal r <= {max_r_inv:.1f} deg)"
            )
            axes[0].grid(alpha=0.2)
            fig.colorbar(sc0, ax=axes[0], label="Nominal theta [deg]")

            sc1 = axes[1].scatter(
                r_nom_inv, radial_arcmin, c=theta_nom_inv, s=9, alpha=0.72
            )
            axes[1].axhline(0.0, ls="--", lw=1, alpha=0.6)
            axes[1].set_xlabel("Nominal r [deg]")
            axes[1].set_ylabel("recovered r - nominal r [arcmin]")
            axes[1].grid(alpha=0.2)
            fig.colorbar(sc1, ax=axes[1], label="Nominal theta [deg]")
            _save_report_figure(
                fig, pdf, figures_dir, "12_inverse_angular_residual_field"
            )
            plt.close(fig)

            ring_rows = list(inverse_details["ring_rows"])
            if ring_rows:
                ring_r = np.asarray([row["nominal_r_deg"] for row in ring_rows])
                ring_sigma = np.asarray([row["sigma_arcmin"] for row in ring_rows])
                ring_smooth = np.asarray(
                    [row["smooth_ptp_arcmin"] for row in ring_rows]
                )
                ring_ptp = np.asarray([row["ptp_arcmin"] for row in ring_rows])
                ring_bias = np.asarray(
                    [row["median_bias_arcmin"] for row in ring_rows]
                )
                fig, axes = plt.subplots(4, 1, figsize=(11, 11), sharex=True)
                axes[0].plot(ring_r, ring_sigma, "o-")
                axes[0].set_ylabel("robust sigma [arcmin]")
                axes[0].set_title("Inverse ring reconstruction residual structure")
                axes[1].plot(ring_r, ring_smooth, "o-")
                axes[1].set_ylabel("smooth PTP [arcmin]")
                axes[2].plot(ring_r, ring_ptp, "o-")
                axes[2].set_ylabel("raw PTP [arcmin]")
                axes[3].plot(ring_r, ring_bias, "o-")
                axes[3].axhline(0.0, ls="--", lw=1, alpha=0.6)
                axes[3].set_ylabel("median bias [arcmin]")
                axes[3].set_xlabel("Nominal ring r [deg]")
                for ax in axes:
                    ax.grid(alpha=0.2)
                _save_report_figure(
                    fig, pdf, figures_dir, "13_inverse_ring_structure"
                )
                plt.close(fig)

            spoke_rows = list(inverse_details["spoke_rows"])
            if spoke_rows:
                spoke_theta = np.asarray(
                    [row["nominal_theta_deg"] for row in spoke_rows]
                )
                theta_offset = np.asarray(
                    [row["theta_offset_arcmin"] for row in spoke_rows]
                )
                spoke_sigma = np.asarray(
                    [row["sigma_arcmin"] for row in spoke_rows]
                )
                spoke_smooth = np.asarray(
                    [row["smooth_ptp_arcmin"] for row in spoke_rows]
                )
                spoke_ptp = np.asarray([row["ptp_arcmin"] for row in spoke_rows])
                fig, axes = plt.subplots(4, 1, figsize=(11, 11), sharex=True)
                axes[0].scatter(spoke_theta, theta_offset, s=16)
                axes[0].axhline(0.0, ls="--", lw=1, alpha=0.6)
                axes[0].set_ylabel("theta offset [arcmin]")
                axes[0].set_title("Inverse spoke reconstruction residual structure")
                axes[1].scatter(spoke_theta, spoke_sigma, s=16)
                axes[1].set_ylabel("robust sigma [arcmin]")
                axes[2].scatter(spoke_theta, spoke_smooth, s=16)
                axes[2].set_ylabel("smooth PTP [arcmin]")
                axes[3].scatter(spoke_theta, spoke_ptp, s=16)
                axes[3].set_ylabel("raw PTP [arcmin]")
                axes[3].set_xlabel("Nominal spoke theta [deg]")
                for ax in axes:
                    ax.grid(alpha=0.2)
                _save_report_figure(
                    fig, pdf, figures_dir, "14_inverse_spoke_structure"
                )
                plt.close(fig)

            if calibration.axisymmetric_twist_kind != "none":
                r_grid = np.linspace(
                    0.0,
                    float(calibration.r_nom_max_deg),
                    500,
                )
                twist_deg = calibration.axisymmetric_twist_deg(r_grid)
                fig, ax = plt.subplots(figsize=(10, 5.5))
                ax.plot(r_grid, np.asarray(twist_deg) * 60.0)
                ax.axhline(0.0, ls="--", lw=1, alpha=0.6)
                ax.axvline(max_r_inv, ls=":", lw=1, alpha=0.7)
                ax.set_xlabel("Nominal r [deg]")
                ax.set_ylabel("Axisymmetric twist [arcmin]")
                ax.set_title(
                    "Fitted global axisymmetric twist "
                    f"({calibration.axisymmetric_twist_kind}, "
                    f"scale={calibration.axisymmetric_twist_scale_deg:.1f} deg)"
                )
                ax.grid(alpha=0.2)
                _save_report_figure(
                    fig, pdf, figures_dir, "15_axisymmetric_twist"
                )
                plt.close(fig)

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


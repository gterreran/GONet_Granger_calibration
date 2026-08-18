"""Public, GUI-independent grid-calibration evaluation API.

The :class:`GridCalibration` container is reconstructed entirely from plain
numerical/string data.  Its ``.npz`` representation therefore does not require
pickle and is suitable as a stable interchange artifact for downstream tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import least_squares

from .distortion import evaluate_polar_distortion

CALIBRATION_FORMAT = "grid-calibration"
CALIBRATION_FORMAT_VERSION = 1
IMAGE_COORDINATE_CONVENTION = (
    "x=column,y=row;origin=upper-left;+x=right;+y=down;"
    "pixel-centers-at-integer-coordinates"
)

_REQUIRED_KEYS = {
    "format",
    "version",
    "image_coordinate_convention",
    "sensor_width_px",
    "sensor_height_px",
    "radial_degree",
    "harmonic_radial_degree",
    "harmonic_order",
    "fit_constant_terms",
    "r_nom_max_deg",
    "params_full",
    "param_names",
    "fit_rms_px",
    "fit_median_px",
    "fit_p95_px",
    "fit_max_abs_px",
    "fit_inlier_rms_px",
    "outlier_threshold_px",
    "n_inliers",
    "n_outliers",
    "calibrated_angular_range_deg",
}


def _parameter_names(
    radial_degree: int,
    harmonic_radial_degree: int,
    harmonic_order: int,
    fit_constant_terms: bool,
) -> tuple[str, ...]:
    names = ["cx", "cy", "theta0_deg"]
    names.extend(f"k{p}" for p in range(1, radial_degree + 1))

    start_n = 0 if fit_constant_terms else 1
    for axis in ("dr", "dtan"):
        for m in range(harmonic_radial_degree + 1):
            for n in range(start_n, harmonic_order + 1):
                if n == 0:
                    names.append(f"{axis}_m{m}_c0")
                else:
                    names.append(f"{axis}_m{m}_c{n}")
                    names.append(f"{axis}_m{m}_s{n}")
    return tuple(names)


def _optional_float(value: np.ndarray) -> float | None:
    result = float(np.asarray(value).item())
    return None if np.isnan(result) else result


def _scalar_or_array(value: np.ndarray) -> float | np.ndarray:
    value = np.asarray(value, dtype=float)
    if value.ndim == 0:
        return float(value)
    return value


@dataclass(frozen=True)
class CalibrationFitQuality:
    """Compact fit-quality summary stored in the portable artifact."""

    rms_px: float
    median_px: float
    p95_px: float
    max_abs_px: float
    inlier_rms_px: float | None = None
    outlier_threshold_px: float | None = None
    n_inliers: int = 0
    n_outliers: int = 0


@dataclass(frozen=True)
class GridCalibration:
    """Portable fitted calibration and pixel/angle transform evaluator.

    ``params_full`` follows the parameter ordering recorded in ``param_names``.
    Angles are degrees.  Image coordinates follow
    :data:`IMAGE_COORDINATE_CONVENTION`.
    """

    sensor_width_px: int
    sensor_height_px: int
    radial_degree: int
    harmonic_radial_degree: int
    harmonic_order: int
    fit_constant_terms: bool
    r_nom_max_deg: float
    params_full: np.ndarray
    fit_quality: CalibrationFitQuality
    calibrated_angular_range_deg: tuple[float, float]
    image_coordinate_convention: str = IMAGE_COORDINATE_CONVENTION
    format: str = CALIBRATION_FORMAT
    version: int = CALIBRATION_FORMAT_VERSION

    def __post_init__(self) -> None:
        params = np.asarray(self.params_full, dtype=float)
        object.__setattr__(self, "params_full", params)

        if self.format != CALIBRATION_FORMAT:
            raise ValueError(
                f"Unsupported calibration format {self.format!r}; "
                f"expected {CALIBRATION_FORMAT!r}."
            )
        if int(self.version) != CALIBRATION_FORMAT_VERSION:
            raise ValueError(
                f"Unsupported calibration format version {self.version}; "
                f"expected {CALIBRATION_FORMAT_VERSION}."
            )
        if self.image_coordinate_convention != IMAGE_COORDINATE_CONVENTION:
            raise ValueError(
                "Unsupported image-coordinate convention: "
                f"{self.image_coordinate_convention!r}."
            )
        if self.sensor_width_px <= 0 or self.sensor_height_px <= 0:
            raise ValueError("Sensor dimensions must be positive integers.")
        if self.radial_degree < 1:
            raise ValueError("radial_degree must be at least 1.")
        if self.harmonic_radial_degree < 0 or self.harmonic_order < 0:
            raise ValueError("Harmonic degrees/orders must be non-negative.")
        if not np.isfinite(self.r_nom_max_deg) or self.r_nom_max_deg <= 0:
            raise ValueError("r_nom_max_deg must be a positive finite value.")

        r_min, r_max = map(float, self.calibrated_angular_range_deg)
        if not (np.isfinite(r_min) and np.isfinite(r_max) and 0 <= r_min <= r_max):
            raise ValueError(
                "calibrated_angular_range_deg must contain finite increasing "
                "non-negative radii."
            )
        object.__setattr__(self, "calibrated_angular_range_deg", (r_min, r_max))

        expected_names = self.param_names
        if params.ndim != 1 or params.size != len(expected_names):
            raise ValueError(
                "params_full has the wrong size for this model configuration: "
                f"expected {len(expected_names)}, got {params.size}."
            )
        if not np.all(np.isfinite(params)):
            raise ValueError("params_full contains non-finite values.")

    @property
    def param_names(self) -> tuple[str, ...]:
        """Return the stable parameter ordering implied by the model config."""
        return _parameter_names(
            self.radial_degree,
            self.harmonic_radial_degree,
            self.harmonic_order,
            self.fit_constant_terms,
        )

    @property
    def center_px(self) -> tuple[float, float]:
        """Return the fitted image-space distortion center ``(cx, cy)``."""
        return float(self.params_full[0]), float(self.params_full[1])

    @classmethod
    def from_fit(
        cls,
        *,
        fit_result: Any,
        model: Any,
        data: Any,
        sensor_shape: tuple[int, int],
    ) -> "GridCalibration":
        """Build a portable calibration from the current modeling output."""
        height, width = map(int, sensor_shape)

        inlier_mask = np.asarray(fit_result.inlier_mask, dtype=bool)
        r_nom = np.asarray(data.r_nom_deg, dtype=float)
        if inlier_mask.shape == r_nom.shape and np.any(inlier_mask):
            calibrated_r = r_nom[inlier_mask]
        else:
            calibrated_r = r_nom

        summary = fit_result.summary_full
        inlier_summary = fit_result.summary_full_inliers

        return cls(
            sensor_width_px=width,
            sensor_height_px=height,
            radial_degree=int(model.config.radial_degree),
            harmonic_radial_degree=int(model.config.harmonic_radial_degree),
            harmonic_order=int(model.config.harmonic_order),
            fit_constant_terms=bool(model.config.fit_constant_terms),
            r_nom_max_deg=float(model.r_nom_max_deg),
            params_full=np.asarray(fit_result.params_full, dtype=float),
            fit_quality=CalibrationFitQuality(
                rms_px=float(summary.rms),
                median_px=float(summary.median),
                p95_px=float(summary.p95),
                max_abs_px=float(summary.max_abs),
                inlier_rms_px=(
                    None if inlier_summary is None else float(inlier_summary.rms)
                ),
                outlier_threshold_px=(
                    None
                    if fit_result.outlier_threshold_px is None
                    else float(fit_result.outlier_threshold_px)
                ),
                n_inliers=int(fit_result.n_inliers),
                n_outliers=int(fit_result.n_outliers),
            ),
            calibrated_angular_range_deg=(
                float(np.min(calibrated_r)),
                float(np.max(calibrated_r)),
            ),
        )

    def _forward(self, r_deg: Any, theta_deg: Any) -> dict[str, np.ndarray]:
        return evaluate_polar_distortion(
            params=self.params_full,
            radial_degree=self.radial_degree,
            harmonic_radial_degree=self.harmonic_radial_degree,
            harmonic_order=self.harmonic_order,
            fit_constant_terms=self.fit_constant_terms,
            r_nom_max_deg=self.r_nom_max_deg,
            r_nom_deg=r_deg,
            theta_nom_deg=theta_deg,
        )

    def angle_to_pixel(
        self,
        r_deg: Any,
        theta_deg: Any,
    ) -> tuple[float | np.ndarray, float | np.ndarray]:
        """Map nominal angular polar coordinates to image pixel coordinates."""
        pred = self._forward(r_deg, theta_deg)
        return _scalar_or_array(pred["x_pred"]), _scalar_or_array(pred["y_pred"])

    def _initial_radius_deg(
        self,
        pixel_radius: np.ndarray,
        *,
        max_radius_deg: float,
    ) -> np.ndarray:
        # The dominant symmetric radial model is an excellent initializer.  The
        # dense lookup also remains robust to small higher-order departures from
        # a perfectly linear/equidistant lens model.
        sample_r = np.linspace(0.0, max_radius_deg, 4097)
        u = np.deg2rad(sample_r)
        radial_coeffs = self.params_full[3 : 3 + self.radial_degree]
        sample_rho = np.zeros_like(sample_r)
        for power, coeff in enumerate(radial_coeffs, start=1):
            sample_rho += coeff * u**power

        order = np.argsort(sample_rho)
        rho_sorted = sample_rho[order]
        r_sorted = sample_r[order]
        rho_unique, unique_idx = np.unique(rho_sorted, return_index=True)
        r_unique = r_sorted[unique_idx]
        if rho_unique.size < 2:
            raise ValueError("The fitted radial model cannot be inverted.")

        return np.interp(
            pixel_radius,
            rho_unique,
            r_unique,
            left=r_unique[0],
            right=r_unique[-1],
        )

    def pixel_to_angle(
        self,
        x: Any,
        y: Any,
        *,
        extrapolate: bool = False,
        max_iterations: int = 20,
        tolerance_px: float = 1e-7,
        strict: bool = True,
    ) -> tuple[float | np.ndarray, float | np.ndarray]:
        """Invert image pixels to nominal angular polar coordinates.

        The inverse is solved numerically against the complete fitted forward
        model, including radial and tangential harmonic corrections.  By
        default, solutions are restricted to radii no larger than the calibrated
        outer radius.  Set ``extrapolate=True`` to permit radial extrapolation up
        to 180 degrees.

        Parameters
        ----------
        x, y
            Scalar or broadcast-compatible arrays of image pixel coordinates.
        extrapolate
            Permit solutions beyond the calibrated outer angular radius.
        max_iterations
            Maximum vectorized Newton iterations before a SciPy fallback is used
            for any remaining points.
        tolerance_px
            Pixel-space convergence tolerance.
        strict
            If ``True``, raise :class:`ValueError` when any point cannot be
            inverted to better than ``max(1e-4, 10*tolerance_px)`` pixels.
        """
        x_arr, y_arr = np.broadcast_arrays(
            np.asarray(x, dtype=float),
            np.asarray(y, dtype=float),
        )
        if not (np.all(np.isfinite(x_arr)) and np.all(np.isfinite(y_arr))):
            raise ValueError("Pixel coordinates must be finite.")

        original_shape = x_arr.shape
        x_flat = x_arr.ravel()
        y_flat = y_arr.ravel()

        cx, cy = self.center_px
        theta0_deg = float(self.params_full[2])
        dx = x_flat - cx
        dy = y_flat - cy
        pixel_radius = np.hypot(dx, dy)

        max_radius_deg = (
            180.0
            if extrapolate
            else max(float(self.calibrated_angular_range_deg[1]), 1e-6)
        )
        r = self._initial_radius_deg(pixel_radius, max_radius_deg=max_radius_deg)
        theta = np.rad2deg(np.arctan2(dy, dx)) - theta0_deg

        # Vectorized damped Newton solve.  Each point has an independent 2x2
        # Jacobian, so this is much cheaper than invoking a generic optimizer for
        # every pixel in the common case.
        for _ in range(max(0, int(max_iterations))):
            pred = self._forward(r, theta)
            rx = x_flat - np.asarray(pred["x_pred"])
            ry = y_flat - np.asarray(pred["y_pred"])
            err = np.hypot(rx, ry)
            active = err > tolerance_px
            if not np.any(active):
                break

            r_step = np.maximum(1e-5, 1e-6 * np.maximum(1.0, np.abs(r)))
            theta_step = np.full_like(theta, 1e-5)

            pred_rp = self._forward(r + r_step, theta)
            pred_rm = self._forward(r - r_step, theta)
            pred_tp = self._forward(r, theta + theta_step)
            pred_tm = self._forward(r, theta - theta_step)

            dx_dr = (np.asarray(pred_rp["x_pred"]) - np.asarray(pred_rm["x_pred"])) / (2.0 * r_step)
            dy_dr = (np.asarray(pred_rp["y_pred"]) - np.asarray(pred_rm["y_pred"])) / (2.0 * r_step)
            dx_dt = (np.asarray(pred_tp["x_pred"]) - np.asarray(pred_tm["x_pred"])) / (2.0 * theta_step)
            dy_dt = (np.asarray(pred_tp["y_pred"]) - np.asarray(pred_tm["y_pred"])) / (2.0 * theta_step)

            det = dx_dr * dy_dt - dx_dt * dy_dr
            solvable = active & np.isfinite(det) & (np.abs(det) > 1e-12)
            if not np.any(solvable):
                break

            delta_r = np.zeros_like(r)
            delta_theta = np.zeros_like(theta)
            delta_r[solvable] = (
                rx[solvable] * dy_dt[solvable]
                - dx_dt[solvable] * ry[solvable]
            ) / det[solvable]
            delta_theta[solvable] = (
                dx_dr[solvable] * ry[solvable]
                - rx[solvable] * dy_dr[solvable]
            ) / det[solvable]

            # Limit individual Newton jumps so a poor initializer cannot leap to
            # a different angular branch.
            delta_r = np.clip(delta_r, -10.0, 10.0)
            delta_theta = np.clip(delta_theta, -30.0, 30.0)
            r[solvable] = np.clip(
                r[solvable] + delta_r[solvable],
                0.0,
                max_radius_deg,
            )
            theta[solvable] += delta_theta[solvable]

        final = self._forward(r, theta)
        final_err = np.hypot(
            x_flat - np.asarray(final["x_pred"]),
            y_flat - np.asarray(final["y_pred"]),
        )
        fallback = final_err > tolerance_px

        # Generic least-squares is deliberately a fallback rather than the main
        # path.  It makes edge cases robust while keeping bulk transformations
        # fast enough for downstream star catalogs/tracks.
        for idx in np.flatnonzero(fallback):
            theta_seed = float(theta[idx])

            def residual(v: np.ndarray) -> np.ndarray:
                pred_i = self._forward(v[0], v[1])
                return np.array(
                    [
                        float(np.asarray(pred_i["x_pred"])) - x_flat[idx],
                        float(np.asarray(pred_i["y_pred"])) - y_flat[idx],
                    ]
                )

            result = least_squares(
                residual,
                x0=np.array([r[idx], theta_seed], dtype=float),
                bounds=(
                    np.array([0.0, theta_seed - 180.0]),
                    np.array([max_radius_deg, theta_seed + 180.0]),
                ),
                xtol=1e-12,
                ftol=1e-12,
                gtol=1e-12,
                max_nfev=100,
            )
            r[idx], theta[idx] = result.x
            final_err[idx] = np.hypot(*residual(result.x))

        failure_threshold = max(1e-4, 10.0 * float(tolerance_px))
        failed = ~np.isfinite(final_err) | (final_err > failure_threshold)
        if strict and np.any(failed):
            count = int(np.sum(failed))
            worst = float(np.nanmax(final_err))
            range_note = (
                " Enable extrapolate=True if the pixels lie outside the "
                "calibrated angular footprint."
                if not extrapolate
                else ""
            )
            raise ValueError(
                f"Could not invert {count} pixel coordinate(s) within "
                f"{failure_threshold:g} px; worst residual was {worst:.6g} px."
                + range_note
            )

        r_out = r.reshape(original_shape)
        theta_out = np.mod(theta, 360.0).reshape(original_shape)
        return _scalar_or_array(r_out), _scalar_or_array(theta_out)

    def save(self, path: str | Path) -> Path:
        """Write this calibration as a plain-data, no-pickle ``.npz`` file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        q = self.fit_quality
        np.savez_compressed(
            path,
            format=np.asarray(self.format),
            version=np.asarray(self.version, dtype=np.int64),
            image_coordinate_convention=np.asarray(self.image_coordinate_convention),
            sensor_width_px=np.asarray(self.sensor_width_px, dtype=np.int64),
            sensor_height_px=np.asarray(self.sensor_height_px, dtype=np.int64),
            radial_degree=np.asarray(self.radial_degree, dtype=np.int64),
            harmonic_radial_degree=np.asarray(self.harmonic_radial_degree, dtype=np.int64),
            harmonic_order=np.asarray(self.harmonic_order, dtype=np.int64),
            fit_constant_terms=np.asarray(self.fit_constant_terms, dtype=np.bool_),
            r_nom_max_deg=np.asarray(self.r_nom_max_deg, dtype=float),
            params_full=np.asarray(self.params_full, dtype=float),
            param_names=np.asarray(self.param_names),
            fit_rms_px=np.asarray(q.rms_px, dtype=float),
            fit_median_px=np.asarray(q.median_px, dtype=float),
            fit_p95_px=np.asarray(q.p95_px, dtype=float),
            fit_max_abs_px=np.asarray(q.max_abs_px, dtype=float),
            fit_inlier_rms_px=np.asarray(
                np.nan if q.inlier_rms_px is None else q.inlier_rms_px,
                dtype=float,
            ),
            outlier_threshold_px=np.asarray(
                np.nan
                if q.outlier_threshold_px is None
                else q.outlier_threshold_px,
                dtype=float,
            ),
            n_inliers=np.asarray(q.n_inliers, dtype=np.int64),
            n_outliers=np.asarray(q.n_outliers, dtype=np.int64),
            calibrated_angular_range_deg=np.asarray(
                self.calibrated_angular_range_deg,
                dtype=float,
            ),
        )
        return path

    @classmethod
    def load(cls, path: str | Path) -> "GridCalibration":
        """Load and validate a portable calibration with pickle disabled."""
        path = Path(path)
        with np.load(path, allow_pickle=False) as loaded:
            missing = sorted(_REQUIRED_KEYS.difference(loaded.files))
            if missing:
                raise ValueError(
                    f"Calibration artifact {path} is missing required keys: {missing}."
                )

            format_name = str(np.asarray(loaded["format"]).item())
            version = int(np.asarray(loaded["version"]).item())
            convention = str(np.asarray(loaded["image_coordinate_convention"]).item())

            calibration = cls(
                format=format_name,
                version=version,
                image_coordinate_convention=convention,
                sensor_width_px=int(np.asarray(loaded["sensor_width_px"]).item()),
                sensor_height_px=int(np.asarray(loaded["sensor_height_px"]).item()),
                radial_degree=int(np.asarray(loaded["radial_degree"]).item()),
                harmonic_radial_degree=int(
                    np.asarray(loaded["harmonic_radial_degree"]).item()
                ),
                harmonic_order=int(np.asarray(loaded["harmonic_order"]).item()),
                fit_constant_terms=bool(
                    np.asarray(loaded["fit_constant_terms"]).item()
                ),
                r_nom_max_deg=float(np.asarray(loaded["r_nom_max_deg"]).item()),
                params_full=np.asarray(loaded["params_full"], dtype=float),
                fit_quality=CalibrationFitQuality(
                    rms_px=float(np.asarray(loaded["fit_rms_px"]).item()),
                    median_px=float(np.asarray(loaded["fit_median_px"]).item()),
                    p95_px=float(np.asarray(loaded["fit_p95_px"]).item()),
                    max_abs_px=float(np.asarray(loaded["fit_max_abs_px"]).item()),
                    inlier_rms_px=_optional_float(loaded["fit_inlier_rms_px"]),
                    outlier_threshold_px=_optional_float(
                        loaded["outlier_threshold_px"]
                    ),
                    n_inliers=int(np.asarray(loaded["n_inliers"]).item()),
                    n_outliers=int(np.asarray(loaded["n_outliers"]).item()),
                ),
                calibrated_angular_range_deg=tuple(
                    np.asarray(loaded["calibrated_angular_range_deg"], dtype=float)
                    .reshape(2)
                    .tolist()
                ),
            )

            stored_names = tuple(
                str(name) for name in np.asarray(loaded["param_names"]).tolist()
            )
            if stored_names != calibration.param_names:
                raise ValueError(
                    "Calibration artifact parameter ordering does not match its "
                    "model configuration."
                )

        return calibration


def load_calibration(path: str | Path) -> GridCalibration:
    """Load a portable :class:`GridCalibration` artifact."""
    return GridCalibration.load(path)


def _coerce_calibration(
    calibration: GridCalibration | str | Path,
) -> GridCalibration:
    if isinstance(calibration, GridCalibration):
        return calibration
    return GridCalibration.load(calibration)


def angle_to_pixel(
    r_deg: Any,
    theta_deg: Any,
    calibration: GridCalibration | str | Path,
) -> tuple[float | np.ndarray, float | np.ndarray]:
    """Public forward transform from nominal angular coordinates to pixels."""
    return _coerce_calibration(calibration).angle_to_pixel(r_deg, theta_deg)


def pixel_to_angle(
    x: Any,
    y: Any,
    calibration: GridCalibration | str | Path,
    **kwargs: Any,
) -> tuple[float | np.ndarray, float | np.ndarray]:
    """Public inverse transform from image pixels to nominal angular coordinates."""
    return _coerce_calibration(calibration).pixel_to_angle(x, y, **kwargs)


__all__ = [
    "CALIBRATION_FORMAT",
    "CALIBRATION_FORMAT_VERSION",
    "IMAGE_COORDINATE_CONVENTION",
    "CalibrationFitQuality",
    "GridCalibration",
    "angle_to_pixel",
    "load_calibration",
    "pixel_to_angle",
]

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from grid_calibration import (
    CalibrationFitQuality,
    GridCalibration,
    angle_to_pixel,
    load_calibration,
    pixel_to_angle,
)


def _harmonic_calibration() -> GridCalibration:
    rng = np.random.default_rng(7)
    radial_degree = 3
    dr_m, dr_n = 2, 3
    dt_m, dt_n = 3, 4

    n_dr = (dr_m + 1) * dr_n * 2
    n_dtan = (dt_m + 1) * dt_n * 2
    n_params = 3 + radial_degree + n_dr + n_dtan + 1
    params = np.zeros(n_params, dtype=float)
    params[: 3 + radial_degree] = [510.0, 493.0, 12.5, 325.0, 7.0, -1.5]
    cursor = 3 + radial_degree
    params[cursor : cursor + n_dr + n_dtan] = rng.normal(
        0.0, 0.15, n_dr + n_dtan
    )
    params[-1] = -0.45

    return GridCalibration(
        sensor_width_px=1024,
        sensor_height_px=1000,
        radial_degree=radial_degree,
        radial_harmonic_radial_degree=dr_m,
        radial_harmonic_order=dr_n,
        tangential_harmonic_radial_degree=dt_m,
        tangential_harmonic_order=dt_n,
        fit_constant_terms=False,
        axisymmetric_twist_kind="tanh",
        axisymmetric_twist_scale_deg=20.0,
        r_nom_max_deg=100.0,
        params_full=params,
        fit_quality=CalibrationFitQuality(
            rms_px=0.42,
            median_px=0.31,
            p95_px=0.88,
            max_abs_px=1.7,
            inlier_rms_px=0.35,
            outlier_threshold_px=1.5,
            n_inliers=200,
            n_outliers=4,
            inverse_validation_max_r_deg=70.0,
            inverse_radial_robust_sigma_arcmin=0.8,
            inverse_radial_p95_abs_arcmin=1.6,
            inverse_cross_robust_sigma_arcmin=0.7,
            inverse_cross_p95_abs_arcmin=1.5,
        ),
        calibrated_angular_range_deg=(5.0, 100.0),
    )


def _circular_error_deg(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.abs((a - b + 180.0) % 360.0 - 180.0)


def test_angle_to_pixel_and_pixel_to_angle_round_trip_full_harmonic_model() -> None:
    calibration = _harmonic_calibration()
    rng = np.random.default_rng(12)
    r = rng.uniform(1.0, 98.0, 250)
    theta = rng.uniform(0.0, 360.0, 250)

    x, y = calibration.angle_to_pixel(r, theta)
    recovered_r, recovered_theta = calibration.pixel_to_angle(x, y)

    assert np.max(np.abs(np.asarray(recovered_r) - r)) < 1e-5
    assert np.max(_circular_error_deg(np.asarray(recovered_theta), theta)) < 1e-5


def test_public_transform_functions_support_scalars_and_calibration_paths(
    tmp_path: Path,
) -> None:
    calibration = _harmonic_calibration()
    path = calibration.save(tmp_path / "camera_calibration.npz")

    x, y = angle_to_pixel(42.0, 217.0, path)
    assert isinstance(x, float)
    assert isinstance(y, float)

    recovered_r, recovered_theta = pixel_to_angle(x, y, path)
    assert recovered_r == pytest.approx(42.0, abs=1e-6)
    assert _circular_error_deg(
        np.asarray(recovered_theta), np.asarray(217.0)
    ) == pytest.approx(0.0, abs=1e-6)


def test_portable_calibration_round_trip_requires_no_pickle(tmp_path: Path) -> None:
    calibration = _harmonic_calibration()
    path = calibration.save(tmp_path / "portable_calibration.npz")

    with np.load(path, allow_pickle=False) as loaded:
        assert str(loaded["format"].item()) == "grid-calibration"
        assert int(loaded["version"].item()) == 2
        assert int(loaded["sensor_width_px"].item()) == 1024
        assert int(loaded["sensor_height_px"].item()) == 1000
        assert int(loaded["radial_harmonic_radial_degree"].item()) == 2
        assert int(loaded["tangential_harmonic_order"].item()) == 4
        assert str(loaded["axisymmetric_twist_kind"].item()) == "tanh"
        assert float(loaded["axisymmetric_twist_scale_deg"].item()) == 20.0
        assert loaded["params_full"].dtype.kind == "f"
        assert loaded["param_names"].dtype.kind in {"U", "S"}
        assert loaded["calibrated_angular_range_deg"].tolist() == [5.0, 100.0]

    recovered = load_calibration(path)
    assert recovered.sensor_width_px == calibration.sensor_width_px
    assert recovered.sensor_height_px == calibration.sensor_height_px
    assert recovered.param_names == calibration.param_names
    np.testing.assert_allclose(recovered.params_full, calibration.params_full)
    assert recovered.fit_quality == calibration.fit_quality


def test_version1_portable_artifact_is_migrated_on_load(tmp_path: Path) -> None:
    radial_degree = 3
    harmonic_m = 2
    harmonic_n = 3
    n_field = (harmonic_m + 1) * harmonic_n * 2
    params = np.zeros(3 + radial_degree + 2 * n_field)
    params[: 3 + radial_degree] = [500.0, 500.0, 10.0, 320.0, 6.0, -1.0]

    names = ["cx", "cy", "theta0_deg", "k1", "k2", "k3"]
    for axis in ("dr", "dtan"):
        for m in range(harmonic_m + 1):
            for n in range(1, harmonic_n + 1):
                names += [f"{axis}_m{m}_c{n}", f"{axis}_m{m}_s{n}"]

    path = tmp_path / "legacy_v1.npz"
    np.savez_compressed(
        path,
        format=np.asarray("grid-calibration"),
        version=np.asarray(1, dtype=np.int64),
        image_coordinate_convention=np.asarray(
            "x=column,y=row;origin=upper-left;+x=right;+y=down;"
            "pixel-centers-at-integer-coordinates"
        ),
        sensor_width_px=np.asarray(1000, dtype=np.int64),
        sensor_height_px=np.asarray(1000, dtype=np.int64),
        radial_degree=np.asarray(radial_degree, dtype=np.int64),
        harmonic_radial_degree=np.asarray(harmonic_m, dtype=np.int64),
        harmonic_order=np.asarray(harmonic_n, dtype=np.int64),
        fit_constant_terms=np.asarray(False, dtype=np.bool_),
        r_nom_max_deg=np.asarray(90.0),
        params_full=params,
        param_names=np.asarray(names),
        fit_rms_px=np.asarray(1.0),
        fit_median_px=np.asarray(0.8),
        fit_p95_px=np.asarray(1.5),
        fit_max_abs_px=np.asarray(2.0),
        fit_inlier_rms_px=np.asarray(np.nan),
        outlier_threshold_px=np.asarray(np.nan),
        n_inliers=np.asarray(100, dtype=np.int64),
        n_outliers=np.asarray(0, dtype=np.int64),
        calibrated_angular_range_deg=np.asarray([2.5, 90.0]),
    )

    calibration = GridCalibration.load(path)
    assert calibration.version == 2
    assert calibration.radial_harmonic_radial_degree == harmonic_m
    assert calibration.tangential_harmonic_radial_degree == harmonic_m
    assert calibration.radial_harmonic_order == harmonic_n
    assert calibration.tangential_harmonic_order == harmonic_n
    assert calibration.axisymmetric_twist_kind == "none"
    assert calibration.fit_quality.inverse_cross_p95_abs_arcmin is None


def test_from_fit_exports_inlier_angular_range_and_model_configuration() -> None:
    calibration = _harmonic_calibration()
    summary = SimpleNamespace(rms=0.4, median=0.3, p95=0.8, max_abs=1.5)
    inlier_summary = SimpleNamespace(rms=0.32)
    fit_result = SimpleNamespace(
        params_full=calibration.params_full,
        summary_full=summary,
        summary_full_inliers=inlier_summary,
        inlier_mask=np.array([False, True, True, False]),
        outlier_threshold_px=1.2,
        n_inliers=2,
        n_outliers=2,
    )
    model = SimpleNamespace(
        config=SimpleNamespace(
            radial_degree=calibration.radial_degree,
            radial_harmonic_radial_degree=(
                calibration.radial_harmonic_radial_degree
            ),
            radial_harmonic_order=calibration.radial_harmonic_order,
            tangential_harmonic_radial_degree=(
                calibration.tangential_harmonic_radial_degree
            ),
            tangential_harmonic_order=calibration.tangential_harmonic_order,
            fit_constant_terms=calibration.fit_constant_terms,
            axisymmetric_twist_kind=calibration.axisymmetric_twist_kind,
            axisymmetric_twist_scale_deg=(
                calibration.axisymmetric_twist_scale_deg
            ),
        ),
        r_nom_max_deg=calibration.r_nom_max_deg,
    )
    r_nom = np.array([2.5, 5.0, 95.0, 100.0])
    theta_nom = np.array([0.0, 90.0, 180.0, 270.0])
    x, y = calibration.angle_to_pixel(r_nom, theta_nom)
    data = SimpleNamespace(
        r_nom_deg=r_nom,
        theta_nom_deg=theta_nom,
        x=np.asarray(x),
        y=np.asarray(y),
    )

    exported = GridCalibration.from_fit(
        fit_result=fit_result,
        model=model,
        data=data,
        sensor_shape=(1000, 1024),
    )

    assert exported.calibrated_angular_range_deg == (5.0, 95.0)
    assert exported.r_nom_max_deg == 100.0
    assert exported.sensor_width_px == 1024
    assert exported.sensor_height_px == 1000
    assert exported.fit_quality.inlier_rms_px == pytest.approx(0.32)
    assert exported.fit_quality.inverse_validation_max_r_deg == pytest.approx(70.0)
    assert exported.fit_quality.inverse_cross_p95_abs_arcmin == pytest.approx(
        0.0, abs=1e-5
    )


def test_pixel_to_angle_rejects_pixels_outside_calibrated_radial_footprint() -> None:
    calibration = _harmonic_calibration()
    x, y = calibration.angle_to_pixel(120.0, 45.0)

    with pytest.raises(ValueError, match="extrapolate=True"):
        calibration.pixel_to_angle(x, y)

    recovered_r, recovered_theta = calibration.pixel_to_angle(
        x, y, extrapolate=True
    )
    assert recovered_r == pytest.approx(120.0, abs=1e-5)
    assert _circular_error_deg(
        np.asarray(recovered_theta), np.asarray(45.0)
    ) == pytest.approx(0.0, abs=1e-5)

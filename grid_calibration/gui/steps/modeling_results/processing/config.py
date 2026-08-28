"""Configuration dataclass for the distortion-model basis."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelConfig:
    """Configuration for the distortion model basis.

    The radial and tangential correction fields intentionally have independent
    radial/Fourier complexity. The production defaults were selected from the
    geometric cross-validation campaign described in the calibration docs.
    """

    radial_degree: int = 5

    radial_harmonic_radial_degree: int = 4
    radial_harmonic_order: int = 7

    tangential_harmonic_radial_degree: int = 4
    tangential_harmonic_order: int = 8

    axisymmetric_twist_kind: str = "tanh"
    axisymmetric_twist_scale_deg: float = 20.0

    regularization: float = 1e-3
    fit_constant_terms: bool = False

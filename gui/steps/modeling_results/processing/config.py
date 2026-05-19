from __future__ import annotations

from dataclasses import dataclass

@dataclass
class ModelConfig:
    """Configuration for the distortion model basis."""

    radial_degree: int = 4
    harmonic_radial_degree: int = 3
    harmonic_order: int = 4
    regularization: float = 1e-3
    fit_constant_terms: bool = False


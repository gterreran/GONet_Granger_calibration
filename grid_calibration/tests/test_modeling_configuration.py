from __future__ import annotations

from grid_calibration.gui.steps.modeling_results.params import (
    DEFAULT_PARAMETERS,
    normalize_parameters,
)
from grid_calibration.gui.steps.modeling_results.processing import ModelConfig
from grid_calibration.gui.steps.modeling_results.processing.model import (
    PolarDistortionModel,
)


def test_production_model_defaults_match_validated_configuration() -> None:
    config = ModelConfig()
    assert config.radial_degree == 5
    assert config.radial_harmonic_radial_degree == 4
    assert config.radial_harmonic_order == 7
    assert config.tangential_harmonic_radial_degree == 4
    assert config.tangential_harmonic_order == 8
    assert config.axisymmetric_twist_kind == "tanh"
    assert config.axisymmetric_twist_scale_deg == 20.0

    model = PolarDistortionModel(config=config, r_nom_max_deg=90.0)
    assert model.n_total == 159
    assert model.param_names[-1] == "twist_tanh_amp_deg"


def test_gui_defaults_match_model_defaults() -> None:
    assert DEFAULT_PARAMETERS["radial-degree"] == 5
    assert DEFAULT_PARAMETERS["radial-harmonic-radial-degree"] == 4
    assert DEFAULT_PARAMETERS["radial-harmonic-order"] == 7
    assert DEFAULT_PARAMETERS["tangential-harmonic-radial-degree"] == 4
    assert DEFAULT_PARAMETERS["tangential-harmonic-order"] == 8
    assert DEFAULT_PARAMETERS["axisymmetric-twist-kind"] == "tanh"
    assert DEFAULT_PARAMETERS["axisymmetric-twist-scale-deg"] == 20.0


def test_legacy_shared_harmonic_parameters_preserve_old_model_semantics() -> None:
    params = normalize_parameters(
        {
            "radial-degree": 4,
            "harmonic-radial-degree": 3,
            "harmonic-order": 4,
            "outlier-rejection-sigma": 4.5,
        }
    )
    assert params["radial-harmonic-radial-degree"] == 3
    assert params["radial-harmonic-order"] == 4
    assert params["tangential-harmonic-radial-degree"] == 3
    assert params["tangential-harmonic-order"] == 4
    assert params["axisymmetric-twist-kind"] == "none"

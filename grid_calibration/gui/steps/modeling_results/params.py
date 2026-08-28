# grid_calibration/gui/steps/modeling_results/params.py
"""Default parameters and product-backed parameter loading for model fitting."""

from __future__ import annotations

from .keys import PARAMS_KEY


DEFAULT_PARAMETERS = {
    "regularization": 1e-3,
    "fit-constant-terms": False,
    "axisymmetric-twist-kind": "tanh",
    "axisymmetric-twist-scale-deg": 20.0,
    "max-nfev": 3000,
    "outlier-rejection-floor-px": 2.5,
    "min-inlier-fraction": 0.90,
    "inverse-validation-max-r-deg": 70.0,

    # Interactive model-complexity parameters. These are the production
    # defaults selected from the model-development and geometric-CV campaign.
    "radial-degree": 5,
    "radial-harmonic-radial-degree": 4,
    "radial-harmonic-order": 7,
    "tangential-harmonic-radial-degree": 4,
    "tangential-harmonic-order": 8,
    "outlier-rejection-sigma": 4.5,
}


def normalize_parameters(parameters: dict | None) -> dict:
    """Return a complete current parameter dictionary.

    Older modeling products used one shared harmonic radial degree/order for
    both correction fields and had no axisymmetric twist. When such a product
    is loaded, preserve its original model semantics rather than silently
    upgrading the already-produced fit configuration.
    """
    if parameters is None:
        return DEFAULT_PARAMETERS.copy()

    supplied = dict(parameters)
    normalized = DEFAULT_PARAMETERS.copy()

    legacy_harmonics = (
        "harmonic-radial-degree" in supplied
        or "harmonic-order" in supplied
    ) and not any(
        key in supplied
        for key in (
            "radial-harmonic-radial-degree",
            "radial-harmonic-order",
            "tangential-harmonic-radial-degree",
            "tangential-harmonic-order",
        )
    )

    normalized.update(supplied)

    if legacy_harmonics:
        legacy_m = int(supplied.get("harmonic-radial-degree", 3))
        legacy_n = int(supplied.get("harmonic-order", 4))
        normalized.update(
            {
                "radial-harmonic-radial-degree": legacy_m,
                "radial-harmonic-order": legacy_n,
                "tangential-harmonic-radial-degree": legacy_m,
                "tangential-harmonic-order": legacy_n,
                "axisymmetric-twist-kind": "none",
            }
        )

    return normalized


def load_parameters() -> dict:
    from ....errors import MissingProductError
    from .spec import product_io

    try:
        return normalize_parameters(product_io.load()[PARAMS_KEY])
    except MissingProductError:
        return DEFAULT_PARAMETERS.copy()

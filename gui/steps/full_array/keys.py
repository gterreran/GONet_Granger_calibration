# grid_calibration/gui/steps/full_array/keys.py
"""
Product keys and schema constants for the full-array step.

The full-array product is a per-input NPZ file containing the built full-array
image and diagnostic histogram arrays. These keys define the schema enforced by
:class:`~grid_calibration.gui.workflow.product_io.ProductIO` when products are
loaded or saved through the workflow layer.
"""

try:
    from GONet_Wizard.GONet_utils.src.gonet.config import CHANNEL_NAMES_RAW  # type: ignore
except ModuleNotFoundError:
    CHANNEL_NAMES_RAW = ("blue", "green", "red")
"""
Raw-channel names used to construct diagnostic histogram keys.

When :mod:`GONet_Wizard` is unavailable, a lightweight fallback is used so the
module remains importable in minimal testing and documentation environments.
"""

STEP_KEY = "full-array"
"""
Workflow key for the full-array step.
"""

IMAGE_KEY = "image"
"""
NPZ key containing the two-dimensional full-array image.
"""

REQUIRED_ARRAY_KEYS = (
    IMAGE_KEY,
    *[
        key
        for channel in CHANNEL_NAMES_RAW
        for key in (
            f"raw_hist_bins_{channel}",
            f"raw_hist_density_{channel}",
            f"matched_hist_bins_{channel}",
            f"matched_hist_density_{channel}",
        )
    ],
)
"""
Required keys for a valid full-array product.

The schema includes the full-array image plus per-channel histogram diagnostics
for the raw and matched channel distributions.
"""

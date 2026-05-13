# grid_calibration/gui/steps/full_array/key.py

from GONet_Wizard.GONet_utils.src.gonet.config import CHANNEL_NAMES_RAW # type: ignore

STEP_KEY = "full-array"

IMAGE_KEY = "image"

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
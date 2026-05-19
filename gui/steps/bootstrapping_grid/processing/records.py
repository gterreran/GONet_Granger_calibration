"""Output-record builders for bootstrapped nominal assignments."""

from __future__ import annotations

import numpy as np

from .containers import GridData
from .geometry import point_radius_from_center
from ..params import DEFAULT_PARAMETERS


def build_output_records(nominal_points: GridData, center_xy: np.ndarray) -> list[dict[str, float | int]]:
    """
    Convert complete intersection assignments to the distortion-fit ``data`` list.
    """
    data: list[dict[str, float | int]] = []

    complete = np.isfinite(nominal_points.theta_nom_deg) & np.isfinite(nominal_points.r_nom_deg)
    for pos in np.where(complete)[0]:
        x = float(nominal_points.x[pos])
        y = float(nominal_points.y[pos])
        r = float(point_radius_from_center(x, y, center_xy))
        theta = float((np.degrees(np.arctan2(y - center_xy[1], x - center_xy[0])) + 360.0) % 360.0)

        data.append(
            {
                "idx": int(nominal_points.idx[pos]),
                "pixel_x": x,
                "pixel_y": y,
                "r": r,
                "theta": theta,
                "circle_index": int(np.round(nominal_points.r_nom_deg[pos] / DEFAULT_PARAMETERS["grid_step_deg"])),
                "spoke_index": int(np.round(nominal_points.theta_nom_deg[pos] / DEFAULT_PARAMETERS["grid_step_deg"])),
                "nominal_r": float(nominal_points.r_nom_deg[pos]),
                "nominal_theta": float(nominal_points.theta_nom_deg[pos]),
            }
        )

    return data

"""Parallel execution helpers for bootstrapping spoke tiers."""

from __future__ import annotations

import copy
import logging
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

from .containers import DenseGrid, GridData, SpokeBootstrapResult
from .spokes import bootstrap_spoke_pair

logger = logging.getLogger(__name__)


def build_spoke_tiers() -> list[np.ndarray]:
    """Return hierarchical spoke tiers in the half-plane [0, 180)."""
    tier1 = np.arange(0, 180, 30.0)
    tier2 = np.setdiff1d(np.arange(0, 180, 10.0), tier1)
    tier3 = np.setdiff1d(np.arange(0, 180, 5.0), np.union1d(tier1, tier2))
    tier4 = np.setdiff1d(np.arange(0, 180, 2.5), np.union1d(tier1, np.union1d(tier2, tier3)))
    return [tier1, tier2, tier3, tier4]


def _run_spoke_worker(payload: tuple) -> tuple[float, SpokeBootstrapResult | None, str | None]:
    """
    Process one spoke in a worker process.

    Returns
    -------
    spoke_deg, result, error
    """
    (
        spoke_deg,
        nominal_points,
        dense_points,
        center_xy,
        available_mask,
        spoke_tol_px,
    ) = payload

    try:
        result = bootstrap_spoke_pair(
            spoke_deg=spoke_deg,
            nominal_points=nominal_points,
            dense_points=dense_points,
            center_xy=center_xy,
            available_mask=available_mask,
            spoke_tol_px=spoke_tol_px,
        )
        return float(spoke_deg), result, None
    except Exception as exc:  # noqa: BLE001
        return float(spoke_deg), None, str(exc)


def run_spoke_tier(
    spoke_group: np.ndarray,
    nominal_points: GridData,
    dense_points: DenseGrid,
    center_xy: np.ndarray,
    assigned_spoke_deg: np.ndarray,
    max_workers: int,
    spoke_tol_px: float,
) -> list[SpokeBootstrapResult]:
    """
    Run one spoke tier, optionally in parallel.

    Each worker receives the same availability mask. After the tier finishes,
    duplicate dense-point assignments are discarded before updating the global
    assignment table.
    """
    available_mask = assigned_spoke_deg < 0
    payloads = [
        (
            float(spoke_deg),
            copy.deepcopy(nominal_points) if max_workers > 1 else nominal_points,
            dense_points,
            center_xy,
            available_mask,
            spoke_tol_px,
        )
        for spoke_deg in spoke_group
    ]

    raw_results: list[SpokeBootstrapResult] = []

    if max_workers > 1 and len(payloads) > 1:
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_run_spoke_worker, payload) for payload in payloads]
            for future in as_completed(futures):
                spoke_deg, result, error = future.result()
                if error is not None:
                    logger.info(f"  spoke {spoke_deg:.1f} failed: {error}")
                elif result is not None:
                    raw_results.append(result)
    else:
        for payload in payloads:
            spoke_deg, result, error = _run_spoke_worker(payload)
            if error is not None:
                logger.info(f"  spoke {spoke_deg:.1f} failed: {error}")
            elif result is not None:
                raw_results.append(result)

    if not raw_results:
        return []

    # Discard duplicate dense-point assignments within the tier.
    counts: dict[int, int] = {}
    for result in raw_results:
        for idx in result.assigned_idx:
            counts[int(idx)] = counts.get(int(idx), 0) + 1

    clean_results: list[SpokeBootstrapResult] = []
    n_duplicates = sum(count > 1 for count in counts.values())

    if n_duplicates:
        logger.info(f"  duplicate assignments in tier: {n_duplicates}; discarding duplicates")

    for result in raw_results:
        keep = np.array([counts[int(idx)] == 1 for idx in result.assigned_idx], dtype=bool)
        clean_results.append(
            SpokeBootstrapResult(
                spoke_deg=result.spoke_deg,
                opposite_deg=result.opposite_deg,
                seed_count=result.seed_count,
                assigned_idx=result.assigned_idx[keep],
                assigned_x=result.assigned_x[keep],
                assigned_y=result.assigned_y[keep],
                assigned_side=result.assigned_side[keep],
                curve_x=result.curve_x,
                curve_y=result.curve_y,
                curve_u=result.curve_u,
                inward_growth_steps=result.inward_growth_steps,
                outward_growth_steps=result.outward_growth_steps,
                cutoff_nominal_r_deg=result.cutoff_nominal_r_deg,
                cutoff_pix=result.cutoff_pix,
            )
        )

    clean_results.sort(key=lambda r: r.spoke_deg)
    return clean_results

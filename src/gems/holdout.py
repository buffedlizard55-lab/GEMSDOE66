"""Hide-and-recover holdout splits for fault labels.

Protocol (from the project brief): withhold whole fault segments, remove visible faults
within a buffer of any withheld segment, and derive every catalogue-based feature only
from the visible faults. The pooled DTI is then scored on the withheld segments only.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage


def spatial_block_ids(shape, block_px: int) -> np.ndarray:
    """Integer id per square block of block_px cells (row-major)."""
    h, w = shape
    rows = np.arange(h) // block_px
    cols = np.arange(w) // block_px
    n_cols = int(cols.max()) + 1
    return rows[:, None] * n_cols + cols[None, :]


def split_fault_segments(fault_mask, holdout_fraction: float, buffer_px: int, seed: int) -> dict:
    """Split a binary fault raster into visible faults and withheld segments.

    Segments are 8-connected components. Visible faults that lie within buffer_px of a
    withheld segment are dropped from the visible set and not scored (returned as
    'buffer_dropped'), so no near-duplicate geometry leaks into the features.
    """
    fm = np.asarray(fault_mask, dtype=bool)
    comp, n = ndimage.label(fm, structure=np.ones((3, 3), dtype=int))
    rng = np.random.default_rng(seed)
    k = 0 if n == 0 else max(1, int(round(holdout_fraction * n)))
    held_ids = rng.choice(np.arange(1, n + 1), size=k, replace=False) if k else np.array([], int)
    held_comp = np.isin(comp, held_ids)
    holdout = fm & held_comp
    visible_raw = fm & ~held_comp
    if holdout.any():
        dist_px = ndimage.distance_transform_edt(~holdout)
        buffer_zone = dist_px <= buffer_px
    else:
        buffer_zone = np.zeros_like(fm)
    visible = visible_raw & ~buffer_zone
    buffer_dropped = visible_raw & buffer_zone
    return {
        "visible": visible,
        "holdout": holdout,
        "buffer_dropped": buffer_dropped,
        "held_segment_ids": held_ids.tolist(),
        "n_segments": int(n),
    }


def spatial_block_holdout(fault_mask, lidar_mask, block_px: int, holdout_fraction: float,
                          buffer_px: int, seed: int, min_lidar_fraction: float = 0.9) -> dict:
    """Withhold whole spatial blocks (not fault segments) as the gate requires.

    Only blocks with lidar coverage >= min_lidar_fraction and at least one fault cell are
    eligible. Chosen blocks are withheld entirely; visible faults within buffer_px of a withheld
    block cell are dropped and reported in 'buffer_dropped'. The holdout DTI must be computed
    on the withheld blocks only.
    """
    fm = np.asarray(fault_mask, dtype=bool)
    lm = np.asarray(lidar_mask, dtype=bool)
    if fm.shape != lm.shape:
        raise ValueError(f"fault mask {fm.shape} and lidar mask {lm.shape} differ")
    ids = spatial_block_ids(fm.shape, block_px)
    flat_ids = ids.ravel()
    n_blocks = int(flat_ids.max()) + 1
    lidar_frac = np.bincount(flat_ids, weights=lm.ravel().astype(float), minlength=n_blocks)
    cell_count = np.bincount(flat_ids, minlength=n_blocks).astype(float)
    fault_count = np.bincount(flat_ids, weights=fm.ravel().astype(float), minlength=n_blocks)
    eligible = np.flatnonzero((lidar_frac / np.maximum(cell_count, 1) >= min_lidar_fraction) & (fault_count > 0))
    rng = np.random.default_rng(seed)
    k = 0 if eligible.size == 0 else max(1, int(round(holdout_fraction * eligible.size)))
    chosen = rng.choice(eligible, size=min(k, eligible.size), replace=False) if k else np.array([], int)
    held_block = np.isin(ids, chosen)
    holdout = fm & held_block
    visible_raw = fm & ~held_block
    if holdout.any():
        buffer_zone = ndimage.distance_transform_edt(~holdout) <= buffer_px
    else:
        buffer_zone = np.zeros_like(fm)
    return {
        "visible": visible_raw & ~buffer_zone,
        "holdout": holdout,
        "buffer_dropped": visible_raw & buffer_zone,
        "held_block_ids": sorted(int(c) for c in chosen),
        "eligible_block_count": int(eligible.size),
        "holdout_cells": int(held_block.sum()),
        "holdout_fault_cells": int(holdout.sum()),
    }

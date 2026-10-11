"""Duplicate / lane-drift gate.

The parallel-run protocol for this project requires each submission to be checked against
every raster already in the family registry before it is offered for download:

* rank (Spearman) correlation of the candidate surface with each registry raster's surface;
* the fraction of the candidate's emitted dots that fall within 3 px of a registry raster's
  emitted dots;
* Jaccard overlap of the two positive-pixel sets;
* exact byte-identity (sha256).

The gate trips if the rank correlation exceeds ``max_rho`` (default 0.90) **or** more than
``max_within3`` (default 0.70) of the candidate's dots lie within 3 px of one registry
raster's dots.  If it trips, the candidate is a duplicate of an existing lane and must be
logged as such rather than shipped.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.stats import spearmanr

from .grid import footprint_mask

DEFAULT_MAX_RHO = 0.90
DEFAULT_MAX_WITHIN3 = 0.70
WITHIN_PX = 3.0


def read01(path: Path, fp: np.ndarray) -> np.ndarray:
    with rasterio.open(path) as src:
        a = src.read(1).astype(np.float32)
    a = np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)
    a[~fp] = 0.0
    return np.clip(a, 0.0, 1.0)


def _disc(radius_px: float) -> np.ndarray:
    r = int(np.ceil(radius_px))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    return np.hypot(yy, xx) <= radius_px


def compare(cand: np.ndarray, other: np.ndarray, fp: np.ndarray) -> dict:
    """Surface comparison of two prediction rasters.

    ``frac_*_within_3px`` is reported together with the fraction a **random** dot placement
    would give against the same registry raster.  That null matters: a registry raster with
    311,617 dots covers 6 % of the footprint, so ~83 % of *random* locations already lie
    within 3 px of one of its dots.  Judging overlap without the null flags every candidate
    as a duplicate of the densest file in the registry (registered as IR-66-GATE-01).
    """
    a = np.clip(np.nan_to_num(cand, nan=0.0), 0, 1)
    b = np.clip(np.nan_to_num(other, nan=0.0), 0, 1)
    pa, pb = a > 0, b > 0
    inter = int((pa & pb).sum())
    union = int((pa | pb).sum())
    null_w3 = float((ndimage.binary_dilation(pb, structure=_disc(WITHIN_PX),
                                             border_value=0) & fp).sum() / max(1, fp.sum()))

    # rank correlation over the union of positive supports plus a background sample, so that
    # the statistic is not computed on two sparse identical-by-construction binary masks
    rng = np.random.default_rng(0)
    bg = fp & ~pa & ~pb
    bidx = np.flatnonzero(bg.ravel())
    if bidx.size > 200_000:
        bidx = rng.choice(bidx, 200_000, replace=False)
    sel = np.zeros(a.size, bool)
    sel[np.flatnonzero((pa | pb).ravel())] = True
    sel[bidx] = True
    va, vb = a.ravel()[sel], b.ravel()[sel]
    if np.std(va) == 0 or np.std(vb) == 0:
        rho = 0.0
    else:
        rho = float(spearmanr(va, vb).statistic)

    within3 = 0.0
    if pb.any() and pa.any():
        d = ndimage.distance_transform_edt(~pb)
        within3 = float((d[pa] <= WITHIN_PX).mean())
    return {"jaccard": inter / union if union else 0.0,
            "overlap_frac_of_candidate": inter / max(1, int(pa.sum())),
            "spearman_rho": rho,
            "frac_candidate_dots_within_3px": within3,
            "null_within_3px_random_placement": null_w3,
            "lift_over_random": (within3 / null_w3) if null_w3 > 0 else float("inf"),
            "n_candidate": int(pa.sum()), "n_other": int(pb.sum())}


def check_registry(cand: np.ndarray, registry_dir: Path, fp: np.ndarray | None = None,
                   max_rho: float = DEFAULT_MAX_RHO,
                   max_within3: float = DEFAULT_MAX_WITHIN3,
                   min_lift: float = 1.5) -> dict:
    """Compare a candidate against every raster in the registry.

    The lane-drift gate trips when the candidate is a *systematic* copy of one registry
    raster.  Two things make a copy systematic rather than coincidental:

    * a high rank correlation of the two surfaces (``max_rho``), and
    * an overlap that is high **and** far above what a random placement into the same
      registry raster would produce (``max_within3`` together with ``min_lift``).

    The lift term is required because the registry contains rasters that are 8x denser than
    the candidate; against those, a random placement is already inside the 3 px band most of
    the time, and a naive overlap test flags everything as a duplicate (IR-66-GATE-01).
    """
    fp = footprint_mask() if fp is None else fp
    cand_b = np.asarray(cand, dtype=np.float32)
    cand_sha = hashlib.sha256(np.ascontiguousarray(cand_b).tobytes()).hexdigest()
    rows = []
    worst_rho, worst_lift = 0.0, 0.0
    worst_name_rho, worst_name_lift = "", ""
    identical = []
    for p in sorted(Path(registry_dir).glob("*.tif")):
        o = read01(p, fp)
        if o.max() == 0:
            continue
        r = compare(cand_b, o, fp)
        r["registry_file"] = p.name
        o_sha = hashlib.sha256(np.ascontiguousarray(o).tobytes()).hexdigest()
        r["identical_pixels"] = bool(o_sha == cand_sha)
        if r["identical_pixels"]:
            identical.append(p.name)
        rows.append(r)
        if abs(r["spearman_rho"]) > abs(worst_rho):
            worst_rho, worst_name_rho = r["spearman_rho"], p.name
        lift = r["lift_over_random"]
        if np.isfinite(lift) and lift > worst_lift:
            worst_lift, worst_name_lift = lift, p.name
        del o
    rows.sort(key=lambda r: -abs(r["spearman_rho"]))
    by_lift = sorted(rows, key=lambda r: -r["lift_over_random"])[:5]
    worst_w3 = max(r["frac_candidate_dots_within_3px"] for r in rows) if rows else 0.0
    verdict = "UNIQUE"
    reason = "below every duplicate threshold"
    if identical:
        verdict, reason = "DUPLICATE_EXACT", f"byte-identical to {identical}"
    elif abs(worst_rho) > max_rho:
        verdict, reason = "DUPLICATE_CORRELATION", f"|rho|={abs(worst_rho):.3f} > {max_rho}"
    else:
        flagged = [r for r in rows if r["frac_candidate_dots_within_3px"] > max_within3
                   and r["lift_over_random"] > min_lift]
        if flagged:
            f0 = max(flagged, key=lambda r: r["lift_over_random"])
            verdict = "DUPLICATE_OVERLAP"
            reason = (f"{f0['frac_candidate_dots_within_3px']:.3f} of dots within "
                      f"{WITHIN_PX:g} px of {f0['registry_file']} at "
                      f"{f0['lift_over_random']:.2f}x the random-placement rate")
    return {"verdict": verdict, "reason": reason,
            "max_abs_spearman_rho": float(abs(worst_rho)), "argmax_rho": worst_name_rho,
            "max_frac_dots_within_3px": float(worst_w3),
            "max_lift_over_random": float(worst_lift), "argmax_lift": worst_name_lift,
            "top_by_lift": by_lift,
            "identical_to": identical,
            "thresholds": {"max_rho": max_rho, "max_within3": max_within3,
                           "min_lift": min_lift, "within_px": WITHIN_PX},
            "n_compared": len(rows), "top": rows[:15], "candidate_sha256": cand_sha}

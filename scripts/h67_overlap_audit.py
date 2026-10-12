"""Second, labelled read of the H67-1 registry-overlap result (audit trail).

The H67-1 lane check reports ``max_frac_dots_within_3px = 0.9992`` against one registry raster.
That number is above the project's *raw* stop rule (70 % within 3 px) but below the gate's
lift-adjusted rule (needs > 1.5x the random-placement rate), because the registry contains
rasters whose 3 px dilation covers most of the footprint.  The evidence JSON stores only the
summary row, so this script recomputes the comparison against every registry raster and adds a
**matched null**: the same statistic for a random placement restricted to the eligible band
(LiDAR-valid, outside the exclusion disc) that the emitter actually draws from.

Output: ``evidence/h67_overlap_audit.json``.  Read-only; no submission artifact is written.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.stats import spearmanr

from gemsdoe66.grid import footprint_mask
from gemsdoe66.uniqueness import WITHIN_PX, _disc, read01

ROOT = Path(__file__).resolve().parents[1]
CAND = ROOT / "docs" / "downloads" / "gems66-h67-scarp-lane-novelty-40000dots-v2-zeros.tif"
REG = ROOT / "registry" / "rasters"
OUT = ROOT / "evidence" / "h67_overlap_audit.json"
N_NULL_DRAWS = 3
SEED = 66


def main() -> int:
    fp = footprint_mask()
    with rasterio.open(ROOT / "data" / "raw" / "training_features.tif") as src:
        lidar = src.read(12) > 0
    with rasterio.open(CAND) as src:
        cand = src.read(1).astype(np.float32)
    cand = np.clip(np.nan_to_num(cand, nan=0.0), 0.0, 1.0)
    pa = cand > 0
    elig = fp & lidar
    rng = np.random.default_rng(SEED)
    idx = np.flatnonzero(elig.ravel())
    n_dots = int(pa.sum())
    null_masks = []
    for _ in range(N_NULL_DRAWS):
        m = np.zeros(fp.shape, bool)
        m.ravel()[rng.choice(idx, n_dots, replace=False)] = True
        null_masks.append(m)

    rows = []
    for p in sorted(REG.glob("*.tif")):
        other = read01(p, fp)
        pb = other > 0
        if not pb.any():
            continue
        d = ndimage.distance_transform_edt(~pb)
        w3 = float((d[pa] <= WITHIN_PX).mean())
        null_fp = float((ndimage.binary_dilation(pb, structure=_disc(WITHIN_PX),
                                                 border_value=0) & fp).sum() / fp.sum())
        null_matched = float(np.mean([(d[m] <= WITHIN_PX).mean() for m in null_masks]))
        # rank correlation on the union of supports plus a background sample (same recipe as
        # gemsdoe66.uniqueness.compare, repeated here so the audit is self-contained)
        bg = fp & ~pa & ~pb
        bidx = np.flatnonzero(bg.ravel())
        if bidx.size > 200_000:
            bidx = np.random.default_rng(0).choice(bidx, 200_000, replace=False)
        sel = np.zeros(cand.size, bool)
        sel[np.flatnonzero((pa | pb).ravel())] = True
        sel[bidx] = True
        va, vb = cand.ravel()[sel], other.ravel()[sel]
        rho = 0.0 if (np.std(va) == 0 or np.std(vb) == 0) else float(
            spearmanr(va, vb).statistic)
        inter = int((pa & pb).sum())
        union = int((pa | pb).sum())
        rows.append({
            "registry_file": p.name,
            "n_other_positive": int(pb.sum()),
            "positive_frac_footprint": round(float(pb.sum() / fp.sum()), 4),
            "frac_dots_within_3px": round(w3, 4),
            "null_footprint_random": round(null_fp, 4),
            "lift_footprint": round(w3 / null_fp, 3) if null_fp > 0 else None,
            "null_matched_eligible_random": round(null_matched, 4),
            "lift_matched": round(w3 / null_matched, 3) if null_matched > 0 else None,
            "spearman_rho": round(rho, 4),
            "jaccard": round(inter / union if union else 0.0, 4),
        })
        del other, pb, d

    rows.sort(key=lambda r: -r["frac_dots_within_3px"])
    payload = {
        "schema": "gems-h67-overlap-audit/1",
        "candidate": CAND.name,
        "n_candidate_dots": n_dots,
        "n_compared": len(rows),
        "within_px": WITHIN_PX,
        "null_matched_definition": (
            f"mean fraction of {N_NULL_DRAWS} random {n_dots}-dot placements drawn from the "
            "eligible band (LiDAR-valid, outside the catalogue/SGMC exclusion disc) that land "
            "within 3 px of the registry raster's positive support"),
        "stop_rule": "raw fraction of candidate dots within 3 px of one registry raster > 0.70",
        "lift_rule": "gate trips only when the raw fraction exceeds 0.70 AND lift > 1.5",
        "top_by_within3": rows[:8],
        "top_by_lift": sorted(rows, key=lambda r: -(r["lift_matched"] or 0))[:8],
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(rows)} rasters compared, "
          f"{n_dots:,} candidate dots")
    for r in payload["top_by_within3"][:5]:
        print(f"  {r['registry_file'][:56]:56s} w3={r['frac_dots_within_3px']:.4f} "
              f"nullF={r['null_footprint_random']:.4f} liftF={r['lift_footprint']} "
              f"nullM={r['null_matched_eligible_random']:.4f} liftM={r['lift_matched']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

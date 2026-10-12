#!/usr/bin/env python3
"""E1b - robustness pass on the E1 credit regression.

E1 found |rho| up to 0.96 between owner-reported score and dot-averaged covariates.  With 14
near-identical rasters (37.6-61.3 k unit-mass dots, a 0.04 score spread) that is easy to
over-read, so this pass asks the uncomfortable questions:

1. Are the covariates explainable by plain geography (dot centroid row/column, spread)?
2. Does any covariate survive leave-one-out (LOO) Spearman?
3. Do physical covariates survive *partial* correlation against the dominant spatial axis?
4. Is the implied per-dot credit (c = score*(0.2N + 0.8|G|)/N) consistent with noise?

Outputs evidence/h67_e1b_robustness.json.  Same evidence class as E1:
OWNER-REPORTED-SCORE-ANCHORED ANALYSIS - not a score of anything.
"""
from __future__ import annotations

import json
import csv
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
RAW, EXT, REG, EVID = ROOT / "data" / "raw", ROOT / "data" / "raw" / "external", ROOT / "registry", ROOT / "evidence"
LIDAR_BANDS = ["ex_max", "ex_mean", "step_max", "lapneg_max", "lappos_max", "downface_max",
               "upface_max", "cross_max", "relief", "coh100", "strike", "valid"]
LIDAR_QUANT = {"ex_max": (1.5, "sqrt"), "ex_mean": (0.3, "sqrt"), "step_max": (1.0, "sqrt"),
               "lapneg_max": (0.05, "sqrt"), "lappos_max": (0.05, "sqrt"),
               "downface_max": (1.0, "sqrt"), "upface_max": (1.0, "sqrt"),
               "cross_max": (1.0, "sqrt"), "relief": (300.0, "sqrt"),
               "coh100": (1.0, "linear"), "strike": (180.0, "linear"), "valid": (1.0, "linear")}
BASE_NAMES = ["mag_anom", "rtp", "tmi_hg", "geod_2ndinv", "iso_grav_anom_slope", "tc",
              "geod_shearrate", "geod_dilaterate", "tmi_vg", "deq_n100a15", "iso_grav_anom_vg",
              "det_elev", "iso_grav_anom", "tmi", "depth_to_base_surf", "ieq_n100a15",
              "cond_surf", "iso_grav_anom_hg", "det_elev_slope"]


def read(path, band=1):
    with rasterio.open(path) as src:
        return src.read(band)


def dequant(q, xmax, rule):
    t = (q.astype(np.float32) - 1.0) / 254.0
    x = xmax * (t * t if rule == "sqrt" else t)
    return np.where(q > 0, x, np.nan).astype(np.float32)


def main() -> int:
    e1 = json.loads((EVID / "h67_e1_credit_regression.json").read_text())
    rows = e1["matched_rows"]
    y = np.array([r["owner_reported_score"] for r in rows])
    n_dots = np.array([r["n_dots"] for r in rows], float)

    # ---- layer table (footprint-indexed) -------------------------------------------------
    fp = np.isfinite(read(RAW / "sample_submission.tif"))
    fi = np.flatnonzero(fp.ravel())
    H, W = fp.shape
    rr = (np.arange(H * W) // W)[fi].astype(np.float32)
    cc = (np.arange(H * W) % W)[fi].astype(np.float32)
    layers: dict[str, np.ndarray] = {"ROW": rr, "COL": cc}
    with rasterio.open(RAW / "training_features.tif") as src:
        for i, name in enumerate(BASE_NAMES, start=1):
            a = src.read(i)
            layers["B_" + name] = np.where(np.isfinite(a) & (a > -1e30), a, np.nan).astype(np.float32).ravel()[fi]
    with rasterio.open(EXT / "lidar_scarp_features_u8.tif") as src:
        for i, name in enumerate(LIDAR_BANDS, start=1):
            xmax, rule = LIDAR_QUANT[name]
            layers["L_" + name] = dequant(src.read(i), xmax, rule).ravel()[fi]
    with rasterio.open(EXT / "geodawn_rad_u8.tif") as src:
        for i, name in enumerate(["K", "Th", "U", "TC"], start=1):
            layers["rad_" + name] = (src.read(i).astype(np.float32) / 255.0).ravel()[fi]
    with rasterio.open(EXT / "geodawn_extensions_u8.tif") as src:
        for i, name in enumerate(["ThK", "UK", "UTh", "TMI_up150"], start=1):
            layers["radx_" + name] = (src.read(i).astype(np.float32) / 255.0).ravel()[fi]
    cat = read(RAW / "labels.tif", 1) == 1
    sgmc = read(EXT / "derived_sgmc_faults_100m_u8.tif", 1) > 0
    layers["D_cat"] = ndimage.distance_transform_edt(~cat).ravel()[fi].astype(np.float32)
    layers["D_sgmc"] = ndimage.distance_transform_edt(~sgmc).ravel()[fi].astype(np.float32)
    layers["RHO_cat"] = ndimage.uniform_filter(cat.astype(np.float32), 21, mode="nearest").ravel()[fi]
    layers["RHO_sgmc"] = ndimage.uniform_filter(sgmc.astype(np.float32), 21, mode="nearest").ravel()[fi]
    spring = np.zeros(cat.shape, np.float32)
    with (EXT / "gdr_wellspring_in_footprint.csv").open() as fh:
        for r in csv.DictReader(fh):
            try:
                r0, c0 = int(float(r["row"])), int(float(r["col"]))
            except (ValueError, TypeError):
                continue
            if 0 <= r0 < H and 0 <= c0 < W:
                spring[r0, c0] = 1.0
    layers["D_spring"] = ndimage.distance_transform_edt(spring == 0).ravel()[fi].astype(np.float32)
    layers["RHO_spring"] = ndimage.uniform_filter(spring, 31, mode="nearest").ravel()[fi]

    # ---- per-raster covariates -----------------------------------------------------------
    cov: dict[str, list[float]] = {}
    for r in rows:
        a = np.nan_to_num(read(REG / "rasters" / r["registry_file"], 1).astype(np.float32), nan=0.0)
        ay, ax = np.nonzero(a > 0)
        cov.setdefault("row_mean", []).append(float(ay.mean()))
        cov.setdefault("col_mean", []).append(float(ax.mean()))
        cov.setdefault("row_std", []).append(float(ay.std()))
        cov.setdefault("col_std", []).append(float(ax.std()))
        idx = ay.astype(np.int64) * W + ax
        # map flat (row*W+col) -> footprint index
        pos = np.searchsorted(fi, idx)
        pos = np.clip(pos, 0, fi.size - 1)
        ok = fi[pos] == idx
        idxf = pos[ok]
        for name, vec in layers.items():
            v = vec[idxf]
            fin = np.isfinite(v)
            if fin.any():
                cov.setdefault("mean_" + name, []).append(float(v[fin].mean()))
            if name.startswith("D_"):
                cov.setdefault("frac_" + name + "_le3", []).append(float(np.mean(v[fin] <= 3.0)))
                cov.setdefault("frac_" + name + "_le10", []).append(float(np.mean(v[fin] <= 10.0)))
            if name.startswith("L_"):
                cov.setdefault("p90_" + name, []).append(float(np.nanpercentile(v, 90)))

    def rho(x):
        x = np.asarray(x, float)
        return float(spearmanr(x, y).statistic)

    table = {k: {"values": [float(v) for v in vals], "spearman_rho": rho(vals)} for k, vals in cov.items()
             if len(vals) == len(y)}
    ranked = sorted(table.items(), key=lambda kv: -abs(kv[1]["spearman_rho"]))
    print("--- all covariates by |rho| ---")
    for k, v in ranked[:22]:
        print(f"  rho={v['spearman_rho']:+.3f}  {k}")

    # ---- spatial confound ------------------------------------------------------------------
    conf = {k: table[k]["spearman_rho"] for k in ("row_mean", "col_mean", "row_std", "col_std") if k in table}
    print("\n--- spatial confound ---", {k: round(v, 3) for k, v in conf.items()})

    # ---- partial Spearman against the dominant spatial axis --------------------------------
    def partial(x, z):
        """Spearman partial correlation of x and y controlling for z (rank-residual form)."""
        rx, ry, rz = (np.argsort(np.argsort(v)).astype(float) for v in (np.asarray(x, float), y, np.asarray(z, float)))
        bx = np.polyfit(rz, rx, 1)
        by = np.polyfit(rz, ry, 1)
        return float(np.corrcoef(rx - np.polyval(bx, rz), ry - np.polyval(by, rz))[0, 1])

    ctrl_key = max(("col_mean", "row_mean", "row_std"), key=lambda k: abs(conf.get(k, 0)))
    partials = {k: partial(v["values"], cov[ctrl_key]) for k, v in table.items() if k != ctrl_key}
    partials = dict(sorted(partials.items(), key=lambda kv: -abs(kv[1])))
    print(f"\n--- partial correlation controlling {ctrl_key} (top 15) ---")
    for k, v in list(partials.items())[:15]:
        print(f"  partial={v:+.3f}  (raw {table[k]['spearman_rho']:+.3f})  {k}")

    # ---- LOO robustness of the strongest raw correlations -----------------------------------
    loo = {}
    for k, v in ranked[:20]:
        vals = np.asarray(v["values"], float)
        rhos = []
        for i in range(len(y)):
            m = np.ones(len(y), bool)
            m[i] = False
            rhos.append(float(spearmanr(vals[m], y[m]).statistic))
        loo[k] = {"full": v["spearman_rho"], "loo_min_abs": float(np.min(np.abs(rhos))),
                  "loo_max_abs": float(np.max(np.abs(rhos))),
                  "sign_flips": int(sum(1 for s in rhos if np.sign(s) != np.sign(v["spearman_rho"])))}

    # ---- implied per-dot credit across |G| --------------------------------------------------
    g_profile = {}
    for g in (10_000, 20_000, 30_000, 40_000, 60_000, 100_000):
        c = y * (0.2 * n_dots + 0.8 * g) / n_dots
        g_profile[str(g)] = {"credit_min": float(c.min()), "credit_max": float(c.max()),
                             "credit_mean": float(c.mean()), "credit_cv": float(c.std() / c.mean()),
                             "implied_truth_pixels_if_k_mean_0p5": float(c.mean() / 0.5 * n_dots.mean() / n_dots.mean())}

    out = {
        "schema": "gems-e1b-robustness/1",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "evidence_class": "OWNER-REPORTED-SCORE-ANCHORED ANALYSIS (not a HOLDOUT-DTI, not ORGANIZER-CONFIRMED)",
        "n_rows": len(rows),
        "score_range": [float(y.min()), float(y.max())],
        "dot_count_range": [int(n_dots.min()), int(n_dots.max())],
        "covariate_table": {k: v for k, v in ranked},
        "spearman_vs_score": {k: v["spearman_rho"] for k, v in ranked},
        "spatial_confound": conf,
        "control_variable_used_for_partial": ctrl_key,
        "partial_spearman": partials,
        "leave_one_out": loo,
        "implied_credit_by_G": g_profile,
        "interpretation_guardrails": [
            "Score spread across the 14 matched rasters is only 0.04.",
            "The strongest single explainer is a spatial centroid shift, not a physical layer; every physical layer is collinear with it.",
            "Any coefficient here is a HYPOTHESIS to test on the blocked holdout, never a result.",
            "Per-dot credit differences of <0.01 are inside the noise of a 0.001-quantised leaderboard display.",
        ],
    }
    EVID.mkdir(parents=True, exist_ok=True)
    (EVID / "h67_e1b_robustness.json").write_text(json.dumps(out, indent=1))
    print("\n--- implied per-dot credit by |G| ---")
    for k, v in g_profile.items():
        print(f"  |G|={int(k):>7d}  credit mean={v['credit_mean']:.4f} range=[{v['credit_min']:.4f},{v['credit_max']:.4f}] cv={v['credit_cv']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

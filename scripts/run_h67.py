#!/usr/bin/env python3
"""H67-1 runner - build the lane field, emit the candidate, gate it, write the artifacts.

Steps (all logged to evidence/h67_run.json):

 1. build the pre-registered lane parts (native-resolution scarp channels + scale persistence)
 2. build the novelty habitat term from the E1/E1b owner-reported-anchored model
 3. leakage canary: AUC of every component *alone* against the SGMC off-catalogue truth
 4. compose the field, emit unit-mass dots with greedy minimum separation
 5. uniqueness: pre-placement surface + final dots against every registry raster
 6. write both format siblings with the shared writer, validate with the shared validator
 7. pooled DTI on the blocked LiDAR-covered holdout (negative control, reported not optimised)
 8. run card + evidence

Usage:
    .venv/bin/python scripts/run_h67.py [--dots 40000] [--minsep 3.0] [--dry-run]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gems.submission_writer import sha256_file, write_submission          # noqa: E402
from gems.validate_submission import validate                             # noqa: E402
from gemsdoe66.emission import dot_geometry, greedy_minsep                # noqa: E402
from gemsdoe66.fields import robust_unit                                  # noqa: E402
from gemsdoe66.grid import RAW, footprint_mask                            # noqa: E402
from gemsdoe66.lane67 import lane_parts, persistence_parts, strike_concordance  # noqa: E402
from gemsdoe66.metric import dti_parts                                    # noqa: E402
from gemsdoe66.uniqueness import check_registry                           # noqa: E402

EXT = RAW / "external"
BETA = 0.60          # density modulation strength (see preregistration amendment)
PROC = ROOT / "data" / "processed" / "h67"
EVID = ROOT / "evidence"
REG = ROOT / "registry"


def read(path, band=1):
    with rasterio.open(path) as src:
        return src.read(band)


def rank01(a: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Percentile rank in [0, 1] inside ``mask``; 0 outside. NaN-safe."""
    out = np.zeros(a.shape, np.float32)
    v = a[mask & np.isfinite(a)]
    if v.size == 0:
        return out
    order = np.argsort(v)
    ranks = np.empty(v.size, np.float32)
    ranks[order] = np.linspace(0.0, 1.0, v.size, dtype=np.float32)
    tmp = np.zeros(a.shape, np.float32)
    tmp[mask & np.isfinite(a)] = ranks
    out[mask & np.isfinite(a)] = ranks
    return out if out is not tmp else out


def masked_z(a: np.ndarray, mask: np.ndarray) -> np.ndarray:
    v = a[mask & np.isfinite(a)]
    if v.size == 0:
        return np.zeros(a.shape, np.float32)
    mu, sd = float(np.mean(v)), float(np.std(v))
    z = (a - mu) / max(1e-9, sd)
    return np.where(mask & np.isfinite(a), z, 0.0).astype(np.float32)


def build_field(verbose: bool = True) -> dict:
    fp = footprint_mask()
    PROC.mkdir(parents=True, exist_ok=True)
    parts = lane_parts()
    pers = persistence_parts()
    concord = strike_concordance(parts["dominant_strike_deg"], pers["tensor_strike_deg"])

    # ---- mapped-fault networks (labels / exclusion masks only, never features) -------------
    cat = read(RAW / "labels.tif", 1) == 1
    sgmc = read(EXT / "derived_sgmc_faults_100m_u8.tif", 1) > 0
    mapped = cat | sgmc
    d_mapped = ndimage.distance_transform_edt(~mapped).astype(np.float32)

    # ---- novelty habitat: E1/E1b owner-reported-anchored model, fixed weights --------------
    stack_names = json.loads((ROOT / "data" / "processed" / "stack_names.json").read_text())
    fi = np.load(ROOT / "data" / "processed" / "footprint_index.npy")
    stack = np.lib.format.open_memmap(ROOT / "data" / "processed" / "stack.f32", mode="r",
                                      dtype=np.float32, shape=(len(stack_names), fi.size))
    idx = {n: i for i, n in enumerate(stack_names)}

    def grid(name):
        out = np.full(fp.size, np.nan, np.float32)
        out[fi] = np.asarray(stack[idx[name]])
        return out.reshape(fp.shape)

    deq = grid("deq_n100a15")                    # magnetic Euler-deconvolution depth estimate
    rad_k = grid("rad_K")
    radx_uk = grid("ext_UK")
    lidar_valid = parts["valid"] > 0

    vent = np.zeros(fp.shape, np.float32)
    import csv
    with (EXT / "gdr_volcanic_vents_in_footprint.csv").open() as fh:
        for r in csv.DictReader(fh):
            try:
                r0, c0 = int(float(r["row"])), int(float(r["col"]))
            except (ValueError, TypeError):
                continue
            if 0 <= r0 < fp.shape[0] and 0 <= c0 < fp.shape[1]:
                vent[r0, c0] = 1.0
    d_vent = ndimage.distance_transform_edt(vent == 0).astype(np.float32)
    vent_prox = np.exp(-d_vent / 20.0).astype(np.float32)     # 20 px = 2 km scale

    eligible = fp & lidar_valid
    habitat = (0.40 * rank01(deq, eligible)
               + 0.30 * rank01(rad_k, eligible)
               - 0.30 * rank01(radx_uk, eligible)
               + 0.15 * vent_prox)
    habitat_z = masked_z(habitat, eligible)
    # novelty ramp: 0 at 2 px, 1 by 15 px away from any mapped fault
    novelty = np.clip((d_mapped - 2.0) / 13.0, 0.0, 1.0).astype(np.float32)

    lane = (0.34 * parts["snr_weighted_amplitude"]
            + 0.24 * parts["scarp_pixel_fraction"]
            + 0.20 * parts["orientation_coherence"]
            + 0.22 * pers["persistence"])
    lane_z = masked_z(np.where(eligible, lane, np.nan), eligible)

    # composition: geometric-style blend with a compressed dynamic range (see preregistration)
    z_combined = 0.55 * np.clip(lane_z, -3, 3) + 0.45 * np.clip(habitat_z, -3, 3) * novelty
    field = np.exp(BETA * np.clip(z_combined, -2.5, 2.5))
    field[~eligible] = np.nan
    hedge = np.exp(BETA * np.clip(
        0.6 * masked_z(np.where(fp, pers["persistence"], np.nan), fp)
        + 0.4 * masked_z(np.where(fp, pers["tensor_coherence"], np.nan), fp), -2.5, 2.5))
    hedge[~fp] = np.nan
    parts_out = {"scarp_pixel_fraction": parts["scarp_pixel_fraction"],
                 "snr_weighted_amplitude": parts["snr_weighted_amplitude"],
                 "orientation_coherence": parts["orientation_coherence"],
                 "dominant_strike_deg": parts["dominant_strike_deg"],
                 "step_fraction": parts["step_fraction"],
                 "relief_mean": parts["relief_mean"],
                 "scale_persistence": pers["persistence"],
                 "tensor_coherence": pers["tensor_coherence"],
                 "strike_concordance": concord,
                 "lidar_valid": parts["valid"]}
    np.save(PROC / "field_h67.npy", field.astype(np.float32))
    np.save(PROC / "hedge_h67.npy", hedge.astype(np.float32))
    np.save(PROC / "z_combined.npy", z_combined.astype(np.float32))
    np.save(PROC / "d_mapped.npy", d_mapped.astype(np.float32))
    np.save(PROC / "habitat.npy", habitat.astype(np.float32))
    for k, v in parts_out.items():
        np.save(PROC / f"part_{k}.npy", np.asarray(v, np.float32))
    if verbose:
        print(f"field built: eligible={int(eligible.sum()):,} px, "
              f"finite field={int(np.isfinite(field).sum()):,}, "
              f"p99={np.nanpercentile(field, 99):.3f}")
    return {"field": field, "hedge": hedge, "eligible": eligible, "d_mapped": d_mapped,
            "habitat": habitat, "parts": parts_out, "lane": lane, "cat": cat, "sgmc": sgmc,
            "lidar_valid": lidar_valid, "fp": fp}


def emit_budget(density: np.ndarray, area: np.ndarray, n: int,
                min_sep_px: float, rounds: int = 3) -> np.ndarray:
    """Place ``n`` dots in ``area`` by density-equalising sampling, topping up the gaps.

    The minimum-separation pass discards a few per cent of a systematic sample wherever the
    density is highest, so the placement is repeated on the still-free area until the budget
    is met (or the area is exhausted).
    """
    dots = np.zeros(area.shape, bool)
    for _ in range(rounds):
        short = n - int(dots.sum())
        if short <= 0:
            break
        free = area & ~ndimage.binary_dilation(dots, structure=_disc(min_sep_px)) if dots.any() else area
        got = systematic_sample(density, free, int(round(short * 1.12)), min_sep_px=min_sep_px)
        if not got.any():
            break
        dots |= got
    if int(dots.sum()) > n:                      # trim the tail so the budget is exact
        ys, xs = np.nonzero(dots)
        vals = np.asarray(density, np.float32)[ys, xs]
        drop = np.argsort(vals)[: int(dots.sum()) - n]
        dots[ys[drop], xs[drop]] = False
    return dots


def _disc(radius_px: float) -> np.ndarray:
    r = int(np.ceil(radius_px))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    return np.hypot(yy, xx) <= radius_px


def systematic_sample(density: np.ndarray, eligible: np.ndarray, n_dots: int,
                      min_sep_px: float = 3.0, exclude: np.ndarray | None = None,
                      rounds: int = 4) -> np.ndarray:
    """Density-equalising systematic sample with a hard minimum separation.

    Why this replaces pure greedy packing
    -------------------------------------
    The official metric satisfies DTI = T/(0.2N + 0.8|G|), so the false-positive cost of mass
    depends only on the *number* of emitted dots, while the true-positive credit depends on
    where they are.  Expected DTI is therefore maximised by maximising the sum of the expected
    kernel credit of the chosen cells.  When the posterior density is uncertain, the
    Bayes-shrunk solution is not "the N highest cells" (which clumps and wastes density) but a
    sample whose *local density* follows the (mildly) modulated posterior: coverage of a
    Poisson truth field at fixed N is maximised by a low-discrepancy arrangement, and a
    systematic sample of the cumulative density is exactly that.

    Implementation: walk the eligible cells in row-major order, accumulate the (modulated)
    density, and take the cells where the cumulative mass crosses the evenly spaced quantiles;
    then enforce ``min_sep_px`` by keeping the higher-density cell of any conflicting pair.
    """
    idx = np.flatnonzero(eligible.ravel())
    if idx.size == 0 or n_dots <= 0:
        return np.zeros(eligible.shape, bool)
    dens = np.clip(np.asarray(density, np.float64).ravel()[idx], 0.0, None)
    if dens.sum() <= 0:
        dens = np.ones(idx.size)
    chosen = np.zeros(eligible.size, bool)
    selected_flat = np.flatnonzero(chosen)          # placeholder
    taken = np.zeros(idx.size, bool)
    for _ in range(rounds):
        remaining = n_dots - int(taken.sum())
        if remaining <= 0:
            break
        d = np.where(taken, 0.0, dens)
        if d.sum() <= 0:
            break
        cdf = np.cumsum(d)
        targets = (np.arange(remaining) + 0.5) * (cdf[-1] / remaining)
        sel = np.unique(np.clip(np.searchsorted(cdf, targets), 0, idx.size - 1))
        taken[sel] = True
    flat = np.zeros(eligible.size, np.float32)
    flat[idx[taken]] = np.clip(dens[taken], 1e-9, None)
    field = np.where(flat > 0, flat, np.nan).astype(np.float32).reshape(eligible.shape)
    n = int(np.isfinite(field).sum())
    return greedy_minsep(field, n, eligible, exclude=exclude, min_sep_px=min_sep_px)


def novelty_truth(fp, lidar_valid, min_dist_px=3.0):
    cat = read(RAW / "labels.tif", 1) == 1
    sgmc = read(EXT / "derived_sgmc_faults_100m_u8.tif", 1) > 0
    d_cat = ndimage.distance_transform_edt(~cat)
    return sgmc & (d_cat > min_dist_px) & fp, cat


def leakage_canary(parts_out: dict, truth: np.ndarray, fp: np.ndarray, seed: int = 0) -> dict:
    """AUC of each component ALONE against the SGMC off-catalogue truth (sampled)."""
    from sklearn.metrics import roc_auc_score
    rng = np.random.default_rng(seed)
    pos = np.flatnonzero((truth & fp).ravel())
    neg_pool = np.flatnonzero((fp & ~truth).ravel())
    n_neg = min(150_000, neg_pool.size)
    neg = rng.choice(neg_pool, n_neg, replace=False)
    res = {}
    for name, g in parts_out.items():
        v = np.asarray(g, np.float32).ravel()
        x = v[np.concatenate([pos, neg])]
        y = np.concatenate([np.ones(pos.size), np.zeros(n_neg)])
        ok = np.isfinite(x)
        if ok.sum() < 100 or np.std(x[ok]) == 0:
            continue
        auc = float(roc_auc_score(y[ok], x[ok]))
        res[name] = {"auc": auc, "leakage_flag": bool(max(auc, 1 - auc) > 0.90),
                     "n_pos": int(pos.size), "n_neg_sampled": int(n_neg),
                     "note": "sampled-fold AUC; the truth layer is an inventory, so it is "
                             "a negative control, not a promotion criterion"}
    return res


def pooled_holdout(pred: np.ndarray, fp: np.ndarray, lidar_valid: np.ndarray) -> dict:
    """Pooled DTI on LiDAR-covered blocked holdout vs SGMC off-catalogue truth.

    Four spatial quadrants as independent blocks; each quadrant's truth is the SGMC
    off-catalogue pixels inside that quadrant that are LiDAR-covered; everything else in
    the quadrant (including the mapped catalogue, masked pixel-exactly) is background.
    """
    truth_all, cat = novelty_truth(fp, lidar_valid)
    H, W = fp.shape
    terms = []
    per = {}
    for qy in (0, 1):
        for qx in (0, 1):
            sl = (slice(qy * H // 2, (qy + 1) * H // 2), slice(qx * W // 2, (qx + 1) * W // 2))
            p = np.where(lidar_valid[sl] & fp[sl] & ~cat[sl], np.nan_to_num(pred[sl], nan=0.0), 0.0)
            t = truth_all[sl]
            s, tp, fpw, fnw, ng, S, M = dti_parts(p, t)
            per[f"fold{'NE'[0]}{qy}{qx}"] = {"dti": s, "tpw": tp, "fpw": fpw, "fnw": fnw,
                                             "n_truth": ng, "mass": S}
            terms.append([tp, fpw, fnw, ng])
    T = np.asarray(terms, float)
    tot = T.sum(0)
    pooled = float(tot[0] / (tot[0] + 0.2 * tot[1] + 0.8 * tot[2] + 1e-12))
    rng = np.random.default_rng(0)
    picks = rng.integers(0, T.shape[0], size=(2000, T.shape[0]))
    boot = T[picks].sum(1)
    dti_boot = boot[:, 0] / (boot[:, 0] + 0.2 * boot[:, 1] + 0.8 * boot[:, 2] + 1e-12)
    # range-front stratification: steep + high relief LiDAR-covered cells
    slope = read(RAW / "training_features.tif", 19).astype(np.float32)   # det_elev_slope (band 19)
    relief = np.nan_to_num(read(EXT / "lidar_scarp_features_u8.tif", 9).astype(np.float32) / 255.0)
    thr_s = np.nanpercentile(slope[lidar_valid & fp], 90)
    thr_r = np.nanpercentile(relief[lidar_valid & fp], 80)
    front = lidar_valid & fp & (slope >= thr_s) & (relief >= thr_r)
    strat = {}
    for label, m in (("near_front", front), ("off_front", front is None or ~front)):
        p = np.where(m & ~cat, np.nan_to_num(pred, nan=0.0), 0.0)
        s, tp, fpw, fnw, ng, S, M = dti_parts(p, truth_all)
        strat[label] = {"dti": s, "tpw": tp, "fpw": fpw, "n_truth": ng,
                        "dots": int(((pred > 0) & m).sum())}
    return {"evidence_class": "HOLDOUT-DTI", "positive_control": False,
            "truth": "SGMC 100 m derived faults > 300 m from the competition catalogue, LiDAR-covered",
            "withheld_positive_pixels": int(truth_all.sum()),
            "evaluator_version": "h67-pooled-quadrant-v1",
            "pooled_dti": pooled, "ci95": [float(np.quantile(dti_boot, .025)),
                                           float(np.quantile(dti_boot, .975))],
            "pooled_terms": {"tpw": float(tot[0]), "fpw": float(tot[1]), "fnw": float(tot[2]),
                             "n_truth": int(tot[3])},
            "per_quadrant": per, "stratified": strat,
            "known_limitation": "this instrument is anti-correlated with the owner-reported "
                                "outcome (see evidence/h67_e2_proxy_concordance.json); it is "
                                "reported as a negative control and is NOT a promotion gate",
            "negative_control_reason": "the organiser truth is defined as faults absent from the "
                                       "public fault databases, so SGMC-mapped faults are by "
                                       "construction not truth and mass near them is charged FP"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dots", type=int, default=40000)
    ap.add_argument("--minsep", type=float, default=3.0)
    ap.add_argument("--exclude-px", type=float, default=4.0)
    ap.add_argument("--hedge", type=float, default=0.15,
                    help="fraction of the budget placed off the LiDAR band as a hedge")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tag", default=None)
    args = ap.parse_args()

    t0 = time.time()
    B = build_field()
    field, fp, d_mapped = B["field"], B["fp"], B["d_mapped"]
    eligible = B["eligible"]
    truth, cat = novelty_truth(fp, B["lidar_valid"])

    canary = leakage_canary(B["parts"], truth, fp)

    exclude = d_mapped <= args.exclude_px
    n_main = int(round(args.dots * (1.0 - args.hedge)))
    n_hedge = args.dots - n_main
    main_area = eligible & ~exclude
    hedge_area = fp & ~B["lidar_valid"] & ~exclude
    dots = emit_budget(field, main_area, n_main, args.minsep)
    if n_hedge:
        dots |= emit_budget(B["hedge"], hedge_area, n_hedge, args.minsep)
    geom = dot_geometry(dots)
    pred = np.where(dots, 1.0, 0.0).astype(np.float32)
    pred[~fp] = np.nan

    # covariate profile of the candidate (same statistics E1 measured on prior rasters)
    ys, xs = np.nonzero(dots)
    profile = {"n_dots": int(dots.sum()),
               "mean_d_mapped_px": float(d_mapped[ys, xs].mean()),
               "frac_within_3px_of_mapped": float((d_mapped[ys, xs] <= 3).mean()),
               "lidar_valid_fraction": float(B["lidar_valid"][ys, xs].mean()),
               "row_mean": float(ys.mean()), "col_mean": float(xs.mean()),
               "row_std": float(ys.std()), "col_std": float(xs.std()),
               "nn_median_px": geom.get("nn_median_px")}
    b = 186
    H, W = fp.shape
    dots_block = np.add.reduceat(np.add.reduceat(dots.astype(np.int64), np.arange(0, H, b), 0),
                                 np.arange(0, W, 164), 1)
    fp_block = np.add.reduceat(np.add.reduceat(fp.astype(np.int64), np.arange(0, H, b), 0),
                               np.arange(0, W, 164), 1)
    okb = fp_block > 1000
    dens = dots_block[okb] / fp_block[okb]
    profile["block_density_mean"] = float(dens.mean())
    profile["block_density_cv"] = float(dens.std() / max(1e-12, dens.mean()))

    holdout = pooled_holdout(pred, fp, B["lidar_valid"])
    uniq = check_registry(pred.astype(np.float32), REG / "rasters", fp)

    print(f"dots={profile['n_dots']} nn_med={profile['nn_median_px']:.2f} "
          f"lidar={profile['lidar_valid_fraction']:.3f} mean_d_mapped={profile['mean_d_mapped_px']:.1f}px "
          f"cv={profile['block_density_cv']:.2f} pooled_dti={holdout['pooled_dti']:.5f} "
          f"uniq={uniq['verdict']} maxrho={uniq['max_abs_spearman_rho']:.3f} "
          f"maxw3={uniq['max_frac_dots_within_3px']:.3f}")

    out = {"schema": "gems-h67-run/1", "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "seconds": round(time.time() - t0, 1), "args": vars(args),
           "dot_profile": profile, "dot_geometry": geom,
           "leakage_canary": canary, "holdout_negative_control": holdout,
           "uniqueness": {k: v for k, v in uniq.items() if k != "top"},
           "dry_run": bool(args.dry_run)}
    if args.dry_run:
        print(json.dumps({k: out[k] for k in ("dot_profile", "uniqueness")}, indent=1))
        (EVID / "h67_dry_run.json").write_text(json.dumps(out, indent=1))
        return 0

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    base = args.tag or f"gems66-h67-scarp-lane-novelty-{profile['n_dots']}dots-{stamp}"
    outdir = ROOT / "docs" / "downloads"
    outdir.mkdir(parents=True, exist_ok=True)
    receipts = {}
    for suffix, finite_outside in (("nan", False), ("zeros", True)):
        path = outdir / f"{base}-{suffix}.tif"
        pred_in = np.nan_to_num(pred, nan=0.0)
        rec = write_submission(path, pred_in, fp, RAW / "sample_submission.tif", overwrite=True,
                               outside_fill=0.0 if finite_outside else None,
                               name=f"{base}-{suffix}",
                               note=("H67-1 scarp-lane novelty field, LiDAR-derived scarp "
                                     "channels + scale persistence, mapped-fault exclusion; see "
                                     "GEMSDOE66 run card"))
        val = validate(path, reference_path=RAW / "sample_submission.tif",
                       features_path=RAW / "sample_submission.tif",
                       outside_policy="either" if finite_outside else "nan")
        rec_path = path.with_suffix(path.suffix + ".receipt.json")
        rec["validator"] = val                      # keep the verdict next to the bytes
        rec_path.write_text(json.dumps(rec, indent=1))
        receipts[suffix] = {"path": str(path.relative_to(ROOT)), "receipt": rec,
                            "validator": val, "sha256": sha256_file(path)}
        print(f"wrote {path.name}  validator_passed={val['passed']} sha256={receipts[suffix]['sha256'][:12]}")
    out["artifacts"] = receipts
    out["base_name"] = base
    (EVID / "h67_run.json").write_text(json.dumps(out, indent=1))
    print(f"\nevidence/h67_run.json written ({out['seconds']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

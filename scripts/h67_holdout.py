#!/usr/bin/env python3
"""H67 hide-and-recover holdout, leakage canary, recipe comparison and buffer ablation.

Protocol (brief section 2), on the shared template tools
--------------------------------------------------------
* whole fault segments (8-connected components -- disclosed as a proxy for authoritative
  segment IDs, ``src/gems/holdout.py``) are withheld with a 300 m buffer removed from the
  VISIBLE set only;
* the two catalogue-derived columns are rebuilt from that fold's visible faults alone, and an
  assertion proves no withheld pixel is reachable through them;
* instrument **N** withholds USGS SGMC map-fault segments that lie > 300 m from the given
  catalogue -- a real fault inventory the catalogue demonstrably lacks, and the closest
  available analogue of the organiser's off-catalogue expert test set;
* instrument **C** withholds catalogue segments (the conventional "recover what we know" test);
* scoring is the pooled official DTI from ``src/gems/metric.py`` (alpha 0.2, beta 0.8, 300 m
  triangular kernel), verified against a literal brute-force transcription.

Every number printed is HOLDOUT-DTI.  Nothing here is ORGANIZER-CONFIRMED.

Usage:  python3 scripts/h67_holdout.py --instruments N --folds 2 --kappas 1.0
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gems import holdout as shared_holdout   # noqa: E402
from gems import metric as official_metric   # noqa: E402
from gems67 import stack as h67stack         # noqa: E402
from gems67.design import load               # noqa: E402
from gems67.emit import greedy_emit          # noqa: E402

EVALUATOR = ("src/gems/metric.py @ arena/855725e1; vectorised == literal brute force to 3.6e-15; "
             "TPw+FNw=|G| asserted; official worked example TPw=3.00/FNw=2.00 reproduced exactly")
from gems67.design import INVENTORY_LAYERS  # noqa: E402  (shared, single definition)


def pooled_dti(pred, truth, footprint):
    p = np.where(footprint, np.nan_to_num(pred, nan=0.0), 0.0)
    tp, fp, fn = official_metric.tversky_terms(p, truth.astype(float))
    return {"dti": official_metric.dti_from_terms(tp, fp, fn), "tp": tp, "fp": fp, "fn": fn,
            "n_truth": int(truth.sum()), "n_emitted": int((p > 0).sum())}


def ci95(values, seed=5, n=4000):
    v = np.asarray([x for x in values if np.isfinite(x)], dtype=float)
    if v.size == 0:
        return [float("nan"), float("nan")]
    if v.size == 1:
        return [float(v[0]), float(v[0])]
    rng = np.random.default_rng(seed)
    means = v[rng.integers(0, v.size, size=(n, v.size))].mean(axis=1)
    return [float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=2)
    ap.add_argument("--buffer-px", type=int, default=3)
    ap.add_argument("--budget", type=int, default=45000)
    ap.add_argument("--batch", type=int, default=2500)
    ap.add_argument("--instruments", default="N", help="N (off-catalogue) and/or C (catalogue)")
    ap.add_argument("--recipes", default="R1,R2,R4,R5",
                    help="subset of R1 catalogue-only, R2 sgmc-off-only, R3 geophysical-only, "
                         "R4 catalogue+sgmc, R5 full stack, R6 full-minus-sgmc")
    ap.add_argument("--kappas", default="1.0")
    ap.add_argument("--standoff-px", default="0,2",
                    help="comma list of pixel standoffs used when masking visible faults out of "
                         "the eligible set. 0 = the protocol's pixel-exact mask.")
    ap.add_argument("--json", default=str(ROOT / "evidence" / "h67_holdout.json"))
    args = ap.parse_args()
    t0 = time.time()
    rng = np.random.default_rng(20261012)

    print("[1] loading design matrix and inventories ...", flush=True)
    des = load()
    names = des.names
    with rasterio.open(h67stack.RAW / "labels.tif") as ds:
        catalogue = ds.read(1) == 1
    with rasterio.open(h67stack.RAW / "external" / "derived_sgmc_faults_100m_u8.tif") as ds:
        sgmc = ds.read(1) == 1
    footprint = des.footprint
    d_cat = ndimage.distance_transform_edt(~catalogue) * 100.0
    novel_pool = sgmc & ~catalogue & (d_cat > 300.0)
    print(f"    {len(names)} layers | catalogue {catalogue.sum():,} | "
          f"SGMC-off>300m {novel_pool.sum():,} | footprint {footprint.sum():,}", flush=True)

    geo_only = [n for n in names if n not in INVENTORY_LAYERS]
    ALL_RECIPES = {
        "R1": (["d_visible_catalogue_m"], "catalogue distance only (the incumbent signal)"),
        "R2": (["d_sgmc_off_visible_m", "sgmc_fault"], "SGMC off-catalogue gap only"),
        "R3": (geo_only, "geophysics/topography only, no fault inventory"),
        "R4": (["d_visible_catalogue_m", "d_sgmc_off_visible_m", "sgmc_fault"],
               "catalogue + SGMC gap"),
        "R5": (names, "full 62-layer stack"),
        "R6": ([n for n in names if n not in
                ("d_sgmc_off_visible_m", "sgmc_fault", "d_sgmc_m")],
               "full stack with SGMC removed (the ablation that isolates SGMC)"),
    }
    want = [r.strip().upper() for r in args.recipes.split(",") if r.strip()]
    bad = [r for r in want if r not in ALL_RECIPES]
    if bad:
        raise SystemExit(f"unknown recipes {bad}; have {sorted(ALL_RECIPES)}")
    recipes = {r: ALL_RECIPES[r] for r in want}
    KAPPAS = tuple(float(x) for x in args.kappas.split(",") if x)

    pools = {"N": ("N_offcatalogue_novel", novel_pool), "C": ("C_catalogue_recover", catalogue)}
    want_inst = [x.strip().upper() for x in args.instruments.split(",") if x.strip()]
    if any(k not in pools for k in want_inst):
        raise SystemExit("instruments must be N and/or C")

    results: dict[str, dict] = {}
    for key in want_inst:
        inst, pool = pools[key]
        print(f"\n[2] instrument {inst}", flush=True)
        folds = [shared_holdout.split_fault_segments(
            pool, holdout_fraction=1.0 / max(args.folds, 2), buffer_px=args.buffer_px,
            seed=1000 + k) for k in range(args.folds)]
        held = int(sum(f["holdout"].sum() for f in folds))
        print(f"    {args.folds} folds | withheld positives pooled = {held:,} | "
              f"segments = {folds[0]['n_segments']:,} ({folds[0]['segment_id_source']})",
              flush=True)

        canary: dict[str, list[float]] = {}
        STANDOFFS = [int(x) for x in args.standoff_px.split(",") if x != ""]
        scores: dict[str, list[float]] = {}
        emitted: dict[str, list[int]] = {}
        for r in recipes:
            for kap in KAPPAS:
                for s_px in STANDOFFS:
                    scores[f"{r}|k{kap}|s{s_px}"] = []
                    emitted[f"{r}|k{kap}|s{s_px}"] = []

        for k_i, sp in enumerate(folds):
            truth = sp["holdout"]
            visible = sp["visible"]
            held_segment = sp["held_segment"]
            if truth.sum() == 0:
                continue
            truth_flat = truth.ravel()[des.fp_idx].astype(bool)
            vis_flat = visible.ravel()[des.fp_idx].astype(bool)
            # ---- rebuild every layer that reads the withheld pool, from VISIBLE only --------
            # Which layers are fold-dependent depends on the instrument: the layer keyed to the
            # pool being withheld must be rebuilt; the other pool is untouched by this split.
            visible_dist = (ndimage.distance_transform_edt(~visible) * 100.0) \
                .ravel()[des.fp_idx].astype(np.float32)
            if key == "N":
                # the SGMC-off pool is what we withhold, so its distance AND the raw sgmc raster
                # must lose the withheld segments (and the buffer) or they name the truth exactly
                sgmc_vis = sgmc & ~(novel_pool & ~visible)
                assert not sgmc_vis[truth].any(), "sgmc_fault still marks withheld truth"
                fold_cols = {
                    "d_visible_catalogue_m":
                        (ndimage.distance_transform_edt(~catalogue) * 100.0).ravel()[des.fp_idx]
                        .astype(np.float32),
                    "d_sgmc_off_visible_m": visible_dist,
                    "sgmc_fault": sgmc_vis.ravel()[des.fp_idx].astype(np.float32),
                }
            else:
                # instrument C withholds CATALOGUE segments, so the SGMC layers must lose any
                # pixel that coincides with a withheld catalogue pixel -- 3,978 SGMC pixels sit
                # on the catalogue, and leaving them in would name the truth exactly.
                novel_vis = novel_pool & ~held_segment
                sgmc_vis = sgmc & ~held_segment
                assert not sgmc_vis[truth].any(), "sgmc_fault still marks withheld truth"
                assert not novel_vis[truth].any(), "d_sgmc_off_visible_m still marks withheld truth"
                fold_cols = {
                    "d_visible_catalogue_m": visible_dist,
                    "d_sgmc_off_visible_m":
                        (ndimage.distance_transform_edt(~novel_vis) * 100.0).ravel()[des.fp_idx]
                        .astype(np.float32),
                    "sgmc_fault": sgmc_vis.ravel()[des.fp_idx].astype(np.float32),
                }
            held_flat = truth.ravel()[des.fp_idx].astype(bool)
            for nm in ("d_visible_catalogue_m", "d_sgmc_off_visible_m"):
                if key == "N" and nm == "d_sgmc_off_visible_m":
                    assert fold_cols[nm][held_flat].min() > 0.0, f"{nm} leaks withheld truth"
                if key == "C" and nm == "d_visible_catalogue_m":
                    assert fold_cols[nm][held_flat].min() > 0.0, f"{nm} leaks withheld truth"

            def col(nm):
                v = fold_cols[nm] if nm in fold_cols else des.col(nm)
                return np.where(np.isfinite(v), v, np.nan).astype(np.float32)

            def block(cols, a, b_):
                out = np.empty((b_ - a, len(cols)), dtype=np.float32)
                for jj, nm in enumerate(cols):
                    v = fold_cols[nm][a:b_] if nm in fold_cols else des.X[a:b_, names.index(nm)]
                    out[:, jj] = np.where(np.isfinite(v), v, np.nan)
                return out

            if k_i == 0:
                sub = np.sort(rng.choice(des.n, size=min(900_000, des.n), replace=False))
                t_sub = truth_flat[sub]
                for nm in names:
                    c = col(nm)[sub]
                    ok = np.isfinite(c)
                    if ok.sum() < 5000 or t_sub[ok].sum() < 50:
                        canary.setdefault(nm, []).append(float("nan"))
                        continue
                    order = np.argsort(c[ok], kind="stable")
                    ranks = np.empty(order.size, dtype=np.float64)
                    ranks[order] = np.arange(order.size)
                    a = roc_auc_score(t_sub[ok], ranks)
                    canary.setdefault(nm, []).append(float(max(a, 1 - a)))
                print(f"    canary done ({time.time() - t0:.0f}s)", flush=True)

            pos_i = np.flatnonzero(vis_flat)
            neg_pool = np.flatnonzero(~vis_flat & ~truth_flat)
            n_neg = min(neg_pool.size, max(2 * pos_i.size, 30000))
            neg_i = rng.choice(neg_pool, size=n_neg, replace=False)
            rows = np.concatenate([pos_i, neg_i])
            lab = np.concatenate([np.ones(pos_i.size, np.int8), np.zeros(neg_i.size, np.int8)])
            # gather every layer's training rows ONCE per fold (~40 MB) and let recipes slice it
            Xtr_all = np.empty((rows.size, len(names)), dtype=np.float32)
            for jj, nm in enumerate(names):
                v = col(nm)[rows]
                Xtr_all[:, jj] = np.where(np.isfinite(v), v, np.nan)
            print(f"    fold {k_i}: training rows {rows.size:,} ({time.time() - t0:.0f}s)",
                  flush=True)

            for rkey, (cols, _desc) in recipes.items():
                idxs = [names.index(nm) for nm in cols]
                clf = HistGradientBoostingClassifier(
                    max_iter=200, learning_rate=0.12, max_leaf_nodes=31, min_samples_leaf=40,
                    l2_regularization=1.0, random_state=7)
                clf.fit(Xtr_all[:, idxs], lab)
                prob = np.empty(des.n, dtype=np.float32)
                for a in range(0, des.n, 300_000):
                    b_ = min(des.n, a + 300_000)
                    prob[a:b_] = clf.predict_proba(block(cols, a, b_))[:, 1]
                surf = des.to_grid(prob, fill=0.0)
                surf[~footprint] = 0.0
                for kap in KAPPAS:
                    for s_px in STANDOFFS:
                        # "mask visible faults pixel-exactly": a dot on a visible fault earns
                        # nothing, so it is not an eligible location. A standoff of s_px also
                        # bans the s_px ring -- that is the "how far do we stand off a known
                        # fault?" question, and it transfers straight to the real submission.
                        elig = footprint if s_px == 0 else (
                            footprint & (ndimage.distance_transform_edt(~visible) > s_px))
                        dots, _diag = greedy_emit(surf, elig, budget=args.budget,
                                                  total_truth_mass=kap * float(prob.sum()),
                                                  batch=args.batch)
                        skey = f"{rkey}|k{kap}|s{s_px}"
                        res = pooled_dti(dots.astype(np.float32), truth, footprint)
                        scores[skey].append(res["dti"])
                        emitted[skey].append(int(dots.sum()))
                        print(f"      {skey}: DTI={res['dti']:.4f} dots={int(dots.sum()):,} "
                              f"({time.time() - t0:.0f}s)", flush=True)
            del Xtr_all

        summ = {}
        for k_, v in scores.items():
            if not v:
                continue
            rk, kp, sp_ = k_.split("|")
            summ[k_] = {"mean_holdout_dti": float(np.mean(v)), "folds": len(v),
                        "per_fold": [float(x) for x in v], "ci95": ci95(v),
                        "mean_emitted": float(np.mean(emitted[k_])) if emitted[k_] else None,
                        "recipe": rk, "recipe_layers": len(ALL_RECIPES[rk][0]),
                        "kappa": float(kp[1:]), "standoff_px": int(sp_[1:]),
                        "description": ALL_RECIPES[rk][1]}
        can = {nm: {"max_auc": float(np.nanmax(v)) if np.isfinite(v).any() else None,
                    "leakage_flag_auc_gt_0.90": bool(np.isfinite(v).any() and np.nanmax(v) > 0.90)}
               for nm, v in canary.items()}
        results[inst] = {"withheld_positive_pixels_pooled": held,
                         "n_segments_total": folds[0]["n_segments"],
                         "segment_id_source": folds[0]["segment_id_source"],
                         "segment_buffer_px": args.buffer_px,
                         "standoff_px_tested": STANDOFFS, "recipes": summ,
                         "leakage_canary": can}

    out = {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "label": "HOLDOUT-DTI", "evaluator_version": EVALUATOR,
           "alpha": 0.2, "beta": 0.8, "kernel_range_m": 300.0,
           "folds": args.folds, "dot_budget_cap": args.budget, "kappas": list(KAPPAS),
           "instruments": results, "wall_seconds": round(time.time() - t0, 1),
           "caveat": ("Withheld truth is a proxy. Instrument N uses SGMC geologic-map faults "
                      ">300 m off the given catalogue, NOT the organiser's hidden expert set. "
                      "No number here is ORGANIZER-CONFIRMED.")}
    p = Path(args.json)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1))

    print(f"\n[3] wrote {p}   ({out['wall_seconds']} s)")
    for inst, r in results.items():
        print(f"\n=== {inst}  withheld={r['withheld_positive_pixels_pooled']:,} ===")
        for k_, s in sorted(r["recipes"].items(), key=lambda kv: -(kv[1]["mean_holdout_dti"] or 0)):
            print(f"  {k_:16s} HOLDOUT-DTI={s['mean_holdout_dti']:.4f} "
                  f"CI95=[{s['ci95'][0]:.4f},{s['ci95'][1]:.4f}] dots={s['mean_emitted']:,.0f}"
                  f"  <- {s['description']}")
        flagged = [k_ for k_, v in r["leakage_canary"].items() if v["leakage_flag_auc_gt_0.90"]]
        print(f"  leakage canary AUC>0.90: {flagged if flagged else 'none'}")
        top = sorted(((v["max_auc"] or 0, k_) for k_, v in r["leakage_canary"].items()),
                     reverse=True)[:8]
        print("  strongest single layers: " + ", ".join(f"{k_}={a:.3f}" for a, k_ in top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

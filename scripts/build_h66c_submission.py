#!/usr/bin/env python3
"""Build the H66-C final candidate raster on the official grid.

Differences from the experiment run (``run_h66c.py``), all of them deliberate:

* the field is refit with the **whole** public catalogue as the positive set,
  because at submission time the entire public database is visible -- the
  experiment's held-out half was only there to create a scoring instrument;
* the gap weight uses the distance to the **whole** public catalogue;
* emission geometry is the arm selected out-of-sample in
  ``evidence/h66c_experiment3.json`` (budget 42 000, minimum separation 4 cells,
  hard 200 m catalogue exclusion ramping to full credit at 600 m).

Nothing here reads a withheld pixel, and no withheld-catalogue pixel is used to
make an eligibility, distance, feature, threshold or placement decision.
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
from scipy import ndimage as ndi
from scipy.spatial import cKDTree
from sklearn.ensemble import HistGradientBoostingClassifier

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gemsdoe66.grid import PROCESSED, RAW, canonical_grid, footprint_mask  # noqa: E402
from gemsdoe66.experiment66c import (  # noqa: E402
    load_context, build_matrix, poisson_dots)
from gems.submission_writer import write_submission  # noqa: E402
from gems.validate_submission import validate, footprint_from_features  # noqa: E402


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=42000)
    ap.add_argument("--sep", type=int, default=4)
    ap.add_argument("--gap-hard", type=float, default=200.0)
    ap.add_argument("--gap-ref", type=float, default=600.0)
    ap.add_argument("--seed", type=int, default=20261012)
    ap.add_argument("--neg-ratio", type=int, default=6)
    ap.add_argument("--outdir", default="artifacts/h66c")
    ap.add_argument("--name", default=None)
    ap.add_argument("--note", default=None)
    args = ap.parse_args()

    t0 = time.time()
    grid = canonical_grid()
    ctx = load_context()
    # The official study area is the training-features footprint (the convention the
    # shared validator and the reference solution use).  It differs from the
    # sample_submission finite mask by ~4.6 k cells; see the irregularity register.
    fp = footprint_from_features(RAW / "training_features.tif", shape_hw=grid.shape)
    sample_fp = ctx["fp"]
    ctx["fp"] = fp
    catalogue = ctx["catalogue"]
    lut_full = np.full(fp.size, -1, np.int64)
    fi = np.flatnonzero(fp.ravel()).astype(np.int64)
    lut_full[fi] = np.arange(fi.size)

    z = np.load(PROCESSED / "scarp_channels.npz")
    ch = {k: z[k] for k in z.files}
    covered = ch["covered"].astype(bool)
    cul_veto = ch["cul_veto"].astype(bool)

    d_cat = ndi.distance_transform_edt(~catalogue).astype(np.float32) * 100.0
    X, names = build_matrix(ch, ctx, d_cat, args.gap_ref,
                            out_path=PROCESSED / "X_h66c_final.f32")
    drop = [j for j, n in enumerate(names) if n in ("cat_dist_m", "cat_gap", "cat_density")]
    keep = [j for j in range(len(names)) if j not in drop]

    rng = np.random.default_rng(args.seed)
    pos_ids = lut_full[np.flatnonzero((catalogue & fp & ~cul_veto).ravel())]
    pos_ids = pos_ids[pos_ids >= 0]
    far = fp & (d_cat > 600.0) & (ndi.distance_transform_edt(~ctx["sgmc"]).astype(np.float32)
                                  * 100.0 > 300.0) & ~cul_veto
    far_idx = lut_full[np.flatnonzero(far.ravel())]
    far_idx = far_idx[far_idx >= 0]
    n_neg = min(len(far_idx), args.neg_ratio * int(pos_ids.size))
    neg_idx = rng.choice(far_idx, n_neg, replace=False)
    rows = np.r_[pos_ids, neg_idx]
    Xtr = np.empty((rows.size, len(keep)), np.float32)
    for a, j in enumerate(keep):
        Xtr[:, a] = X[j][rows]
    ytr = np.r_[np.ones(pos_ids.size), np.zeros(neg_idx.size)]
    clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08, max_depth=None,
                                         max_leaf_nodes=31, min_samples_leaf=40,
                                         l2_regularization=1.0, random_state=args.seed)
    clf.fit(Xtr, ytr)
    del Xtr, ytr
    print(f"[1] fitted field on {pos_ids.size:,} catalogue positives / {neg_idx.size:,} negatives")

    prob = np.full(fp.size, np.nan, np.float32)
    chunk = 400_000
    Xk = np.empty((chunk, len(keep)), np.float32)
    for st in range(0, fi.size, chunk):
        e = min(st + chunk, fi.size)
        blk = Xk[: e - st]
        for a, j in enumerate(keep):
            blk[:, a] = X[j][st:e]
        prob[fi[st:e]] = clf.predict_proba(blk)[:, 1].astype(np.float32)
    prob = prob.reshape(fp.shape)

    gap = np.clip((d_cat - args.gap_hard) / max(args.gap_ref - args.gap_hard, 1.0), 0.0, 1.0)
    gap[d_cat <= args.gap_hard] = 0.0
    domain = fp & ~cul_veto & (gap > 0)
    score = np.where(domain, np.nan_to_num(prob, nan=0.0) * gap, -np.inf).astype(np.float32)
    dots = poisson_dots(score, domain, args.sep, args.budget, seed=args.seed)
    pred = np.where(dots, 1.0, 0.0).astype(np.float32)
    print(f"[2] emitted {int(dots.sum()):,} dots")

    outdir = ROOT / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    digest_src = np.ascontiguousarray(dots)
    short = hashlib.sha256(digest_src.tobytes()).hexdigest()[:12]
    name = args.name or f"gems66-h66c-scarpgap-{int(dots.sum())}-{stamp}-{short}"
    note = args.note or ("h66c lidar scarp diffusion inversion + Steger/Frangi lines, "
                         "TIGER-road masked, 200 m catalogue-gap gate, d4 spacing")
    tif = outdir / f"{name}.tif"
    receipt = write_submission(tif, pred, fp, RAW / "sample_submission.tif",
                               overwrite=True, name=name, note=note)
    print(f"[3] wrote {tif.name}\n    sha256={receipt['sha256']}")

    val = validate(tif, reference_path=RAW / "labels.tif",
                   features_path=RAW / "training_features.tif")
    print(f"[4] validator passed={val['passed']} "
          f"(failures={val['has_failures']}, skipped={val['skipped_checks_mean_unverified']})")
    for c in val["checks"]:
        if c["status"] != "PASS":
            print(f"    {c['status']:8s} {c['check']}: {c['detail']}")

    # continuous surface + diagnostics
    ys, xs = np.nonzero(dots)
    dd, _ = cKDTree(np.c_[ys, xs]).query(np.c_[ys, xs], k=2)
    diag = {
        "dot_count": int(dots.sum()),
        "min_separation_cells": args.sep,
        "median_nn_cells": float(np.median(dd[:, 1])),
        "median_dist_to_catalogue_m": float(np.median(d_cat[dots])),
        "frac_dots_within_200m_of_catalogue": float(np.mean(d_cat[dots] <= 200.0)),
        "frac_dots_on_lidar": float(covered[dots].mean()),
        "median_road_dist_m": float(np.nanmedian(ctx["road"][dots])),
        "median_L_ex_max_at_dots": float(np.nanmedian(ch["amp"][dots])),
        "median_a_hat_at_dots_m": float(np.nanmedian(ch["a_hat"][dots])),
        "median_kt_hat_at_dots_m2": float(np.nanmedian(ch["kt_hat"][dots])),
        "median_steger_amp_at_dots": float(np.nanmedian(ch["steger_amp"][dots])),
        "median_frangi_amp_at_dots": float(np.nanmedian(ch["frangi_amp"][dots])),
        "median_coh100_at_dots": float(np.nanmedian(ch["coh_cell"][dots])),
        "footprint_cells_features_convention": int(fp.sum()),
        "footprint_cells_sample_submission_convention": int(sample_fp.sum()),
        "footprint_disagreement_cells": int((fp ^ sample_fp).sum()),
        "geodawn_block_share": {int(b): float(np.mean(ctx["acq"][dots] == b)) for b in (1, 2, 3, 4)},
        "training": {"n_pos": int(pos_ids.size), "n_neg": int(neg_idx.size),
                     "positive_set": "full public catalogue (labels.tif > 0) minus cultural veto",
                     "negative_set": "cells >600 m from any catalogue or SGMC fault, minus veto"},
        "emission": {"gap_hard_m": args.gap_hard, "gap_ref_m": args.gap_ref,
                     "cultural_veto_cells": int(cul_veto.sum())},
    }
    surface_path = outdir / f"{name}.surface.npy"
    np.save(surface_path, np.where(domain, np.nan_to_num(prob) * gap, 0.0).astype(np.float32))
    diag["surface_file"] = surface_path.name
    diag["surface_sha256"] = sha256_file(surface_path)
    diag["elapsed_s"] = round(time.time() - t0, 1)

    out = {"name": name, "note": note, "note_chars": len(note), "receipt": receipt,
           "validator": val, "diagnostics": diag,
           "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (outdir / f"{name}.manifest.json").write_text(json.dumps(out, indent=1, default=float))
    print(f"[5] manifest {outdir / (name + '.manifest.json')}")
    print(f"    note chars = {len(note)} (limit 140)")
    print(json.dumps(diag, indent=1, default=float))
    return 0 if val["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

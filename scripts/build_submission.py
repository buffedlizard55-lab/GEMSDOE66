#!/usr/bin/env python3
"""Emit the final raster and write the submission GeoTIFF.

Pipeline
--------
1. build / load the chosen belief field (see ``--field``);
2. pack ``--dots`` pixels by decreasing belief with a minimum separation, deleting every
   candidate within ``--prune`` px of the known catalogue so that no mass is spent on faults
   the organiser does not score;
3. write a single-band float32 EPSG:32611 GeoTIFF with NaN outside the footprint;
4. re-open the bytes and run every portal-format check;
5. run the duplicate / lane-drift gate against all 60 registry rasters;
6. write the receipts and the run card.

Usage
-----
    python3 scripts/build_submission.py --field lidar_lane --dots 37654
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

from gemsdoe66.emission import emit  # noqa: E402
from gemsdoe66.grid import catalogue_mask, footprint_mask  # noqa: E402
from gemsdoe66.submission import write_submission  # noqa: E402
from gemsdoe66.uniqueness import check_registry  # noqa: E402
from gemsdoe66.validate_submission import validate, write_receipt  # noqa: E402

DL = ROOT / "docs" / "downloads"
REG = ROOT / "registry" / "rasters"


def rank01(a: np.ndarray, fp: np.ndarray) -> np.ndarray:
    v = np.where(fp & np.isfinite(a), a, np.nan)
    flat = v.ravel()
    ok = np.isfinite(flat)
    out = np.zeros(flat.size, np.float32)
    order = np.argsort(flat[ok], kind="stable")
    ranks = np.empty(ok.sum(), np.float32)
    ranks[order] = np.arange(ok.sum(), dtype=np.float32)
    out[ok] = ranks / max(1.0, ok.sum() - 1)
    return out.reshape(a.shape)


def build_field(name: str, fp: np.ndarray) -> np.ndarray:
    from gemsdoe66.fields import lidar_lane_field
    if name == "lidar_lane":
        f, _ = lidar_lane_field()
        return np.where(np.isfinite(f), f, 0.0).astype(np.float32)
    if name == "catalogue_habitat":
        return np.load(ROOT / "data" / "processed" / "field_global_cat.npy")
    if name == "sgmc_novel":
        return np.load(ROOT / "data" / "processed" / "field_global_sgmc.npy")
    if name.startswith("mix:"):
        # mix:lidar_lane:0.7|catalogue_habitat:0.3
        spec = name[4:]
        acc = np.zeros(fp.shape, np.float32)
        for part in spec.split("|"):
            sub, w = part.rsplit(":", 1)
            acc += float(w) * rank01(build_field(sub, fp), fp)
        return acc
    raise SystemExit(f"unknown field {name!r}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--field", default="lidar_lane")
    ap.add_argument("--dots", type=int, default=37_654)
    ap.add_argument("--min-sep", type=float, default=2.82)
    ap.add_argument("--prune", type=float, default=2.0,
                    help="delete candidates within this many px of a known catalogue fault")
    ap.add_argument("--scatter-sigma", type=float, default=None,
                    help="rank by the field blurred by this sigma (expected truth scatter)")
    ap.add_argument("--slug", default=None)
    ap.add_argument("--modes", default="nan,zeros")
    args = ap.parse_args()

    t0 = time.time()
    fp = footprint_mask()
    cat = catalogue_mask()
    prune = ndimage.binary_dilation(cat, structure=ndimage.generate_binary_structure(2, 1),
                                    iterations=1)
    # disc of radius `prune` px around every catalogue fault
    r = int(np.ceil(args.prune))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    struct = np.hypot(yy, xx) <= args.prune
    exclude = ndimage.binary_dilation(cat, structure=struct, border_value=0)
    print(f"excluded {int(exclude.sum()):,} px within {args.prune} px of the catalogue")

    field = build_field(args.field, fp)
    f2 = field.astype(np.float32).copy()
    f2[~fp] = -np.inf
    dots = emit(f2, args.dots, fp, exclude=exclude, min_sep_px=args.min_sep,
                scatter_sigma=args.scatter_sigma)
    n = int(dots.sum())
    print(f"emitted {n:,} dots")
    if n == 0:
        return 1

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    digest = hashlib.sha256(np.ascontiguousarray(dots.astype(np.uint8)).tobytes()).hexdigest()[:12]
    slug = args.slug or f"gems66-{args.field.replace(':', '-')}-{n}dots-{stamp}-{digest}"
    slug = slug.replace("mix-", "mix")

    receipts = {}
    for mode in args.modes.split(","):
        out = DL / f"{slug}-{mode}.tif"
        rec = write_submission(dots.astype(np.float32), out, mode=mode)
        val = validate(out, mode=mode, require_off_catalogue=args.prune,
                       expected_dots=n, tol_dots=0)
        write_receipt(val, DL / f"checks-{out.name}.json")
        receipts[mode] = {"write": rec, "validate": val}
        print(f"[{mode}] {out.name}  ok={val['ok']}  sha256={rec['sha256'][:16]}…")
        if not val["ok"]:
            for k, v in val["checks"].items():
                if not v:
                    print(f"   FAILED CHECK: {k}")

    # ---- duplicate / lane-drift gate ---------------------------------------------------
    arr = np.where(dots, 1.0, 0.0).astype(np.float32)
    uniq = check_registry(arr, REG, fp)
    (ROOT / "evidence" / f"uniqueness_{slug}.json").write_text(json.dumps(uniq, indent=1))
    print(f"uniqueness verdict: {uniq['verdict']}  "
          f"max|rho|={uniq['max_abs_spearman_rho']:.3f} ({uniq['argmax_rho'][:40]})  "
          f"max within-3px={uniq['max_frac_dots_within_3px']:.3f} ({uniq['argmax_within3'][:40]})")

    # ---- receipt ------------------------------------------------------------------------
    rec = {
        "slug": slug, "field": args.field, "n_dots": n, "min_sep_px": args.min_sep,
        "catalogue_prune_px": args.prune, "scatter_sigma": args.scatter_sigma,
        "generated_utc": stamp, "modes": receipts, "uniqueness": {
            k: uniq[k] for k in ("verdict", "max_abs_spearman_rho", "argmax_rho",
                                 "max_frac_dots_within_3px", "argmax_within3",
                                 "identical_to", "n_compared")},
        "runtime_s": round(time.time() - t0, 1),
    }
    (ROOT / "evidence" / f"submission_{slug}.json").write_text(json.dumps(rec, indent=1))
    (DL / f"{slug}.manifest.json").write_text(json.dumps(rec, indent=1))
    print(json.dumps({k: v for k, v in rec.items() if k != "modes"}, indent=1))
    return 0 if (receipts[args.modes.split(",")[0]]["validate"]["ok"]) else 1


if __name__ == "__main__":
    sys.exit(main())

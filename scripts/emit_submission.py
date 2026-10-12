#!/usr/bin/env python3
"""Emit the LIDAR-01 submission raster from the fitted score field.

Pipeline: score field -> spacing-constrained (Poisson-disk) dot selection -> normalise to
[0, 1] -> float32 single-band GeoTIFF with NaN exactly outside the official footprint ->
local format validation -> JSON receipt.

Usage:
    python3 scripts/emit_submission.py --budget 37654 --sep 2.8 [--score path] [--name ..]
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from gems.submission_writer import write_submission  # noqa: E402
from gems.validate_submission import validate  # noqa: E402
from lane_run_helper import poisson_disk_dots, weighted_disk_dots  # noqa: E402


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", default=str(ROOT / "data" / "derived" / "lane_score.npy"))
    ap.add_argument("--budget", type=int, default=37654)
    ap.add_argument("--sep", type=float, default=2.8)
    ap.add_argument("--gamma", type=float, default=None,
                    help="intensity exponent; None = deterministic top-score greedy")
    ap.add_argument("--seed", type=int, default=4242)
    ap.add_argument("--name", default=None)
    ap.add_argument("--note", default=None)
    ap.add_argument("--outdir", default=str(ROOT / "artifacts" / "lidar01"))
    ap.add_argument("--publish", action="store_true",
                    help="also copy into docs/downloads/ (only do this once the gate is met)")
    args = ap.parse_args()

    t0 = time.time()
    log = lambda m: print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)

    score = np.load(args.score).astype(np.float32)
    with rasterio.open(ROOT / "data" / "sample_submission.tif") as s:
        sample = s.read(1)
    footprint = np.isfinite(sample)
    log(f"score loaded; footprint cells {int(footprint.sum())}")

    if args.gamma is None:
        dots = poisson_disk_dots(score, footprint & np.isfinite(score), args.budget, args.sep)
    else:
        dots = weighted_disk_dots(score, footprint & np.isfinite(score), args.budget,
                                  args.sep, gamma=args.gamma, seed=args.seed)
    n_dots = int(dots.sum())
    log(f"selected {n_dots} dots (budget {args.budget}, separation {args.sep} cells, "
        f"gamma={args.gamma})")

    pred = np.zeros(score.shape, dtype=np.float64)
    pred[dots] = 1.0

    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    name = args.name or f"gems66-lidar01-scarplet-steger-frangi-{n_dots}dots-{ts}"
    note = args.note or (
        "LIDAR-01: slope-aware antislope scarplet template + Steger/Frangi multiscale "
        "line evidence from the 2 m GeoDAWN lidar stack, spacing-constrained dots.")
    if len(note) > 140:
        note = note[:137] + "..."
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    out_tif = outdir / f"{name}.tif"

    receipt = write_submission(out_tif, pred, footprint,
                               ROOT / "data" / "sample_submission.tif",
                               overwrite=True, name=name, note=note)
    log(f"written {out_tif.name} sha256={receipt['sha256'][:16]}...")

    report = validate(out_tif, ROOT / "data" / "labels.tif",
                      ROOT / "data" / "sample_submission.tif")
    passed = bool(report["passed"])
    log(f"validator passed={passed}")

    # zip for the submission form
    import zipfile
    zip_path = out_tif.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(out_tif, arcname=out_tif.name)

    payload = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "name": name,
        "note": note,
        "note_chars": len(note),
        "tif": str(out_tif.relative_to(ROOT)),
        "tif_sha256": sha256_file(out_tif),
        "zip": str(zip_path.relative_to(ROOT)),
        "zip_sha256": sha256_file(zip_path),
        "bytes": out_tif.stat().st_size,
        "dots": n_dots,
        "budget": args.budget,
        "separation_px": args.sep,
        "gamma": args.gamma,
        "seed": args.seed,
        "score_field": str(Path(args.score).relative_to(ROOT)),
        "score_sha256": sha256_file(args.score),
        "footprint_cells": int(footprint.sum()),
        "validator": report,
        "validator_passed": passed,
        "receipt_kind": "local writer/validator receipt; NOT an organizer receipt",
    }
    (outdir / f"{name}.manifest.json").write_text(json.dumps(payload, indent=1))
    print(json.dumps({k: v for k, v in payload.items() if k != "validator"}, indent=1))
    if passed and args.publish:
        dl = ROOT / "docs" / "downloads"
        dl.mkdir(parents=True, exist_ok=True)
        for src in (out_tif, zip_path, outdir / f"{name}.manifest.json"):
            (dl / src.name).write_bytes(src.read_bytes())
        log("published to docs/downloads/")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

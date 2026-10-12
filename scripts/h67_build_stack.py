#!/usr/bin/env python3
"""Stream every H67 layer into one on-disk float32 design matrix over the official footprint.

Usage:  python3 scripts/h67_build_stack.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from gems67 import stack as h67stack          # noqa: E402
from gems67.design import PROC, Design, save  # noqa: E402


def main() -> int:
    t0 = time.time()
    PROC.mkdir(parents=True, exist_ok=True)
    with rasterio.open(h67stack.RAW / "sample_submission.tif") as ds:
        footprint = np.isfinite(ds.read(1).astype(np.float64))
    with rasterio.open(h67stack.RAW / "labels.tif") as ds:
        catalogue = ds.read(1) == 1
    fp_idx = np.flatnonzero(footprint.ravel())
    n = fp_idx.size
    print(f"footprint cells: {n:,}", flush=True)

    # Single streaming pass: each layer's footprint column is written to its own temp file and
    # then concatenated, so neither the full stack nor a second generator pass is needed.
    tmp = PROC / "_cols"
    tmp.mkdir(parents=True, exist_ok=True)
    for f in tmp.glob("*.npy"):
        f.unlink()
    names: list[str] = []
    prov: dict[str, str] = {}
    for name, arr, src in h67stack.iter_layers(visible_faults=catalogue):
        if name == "__footprint__":
            continue
        if name in h67stack.NON_FEATURES or name.endswith("_reread"):
            continue
        col_vec = arr.ravel()[fp_idx].astype(np.float32)
        del arr
        j = len(names)
        np.save(tmp / f"col_{j:03d}.npy", col_vec)
        names.append(name)
        prov[name] = src
        del col_vec
        if (j + 1) % 10 == 0:
            print(f"  {j + 1} layers  {time.time() - t0:.0f}s", flush=True)
    print(f"{len(names)} layers extracted in {time.time() - t0:.0f}s; concatenating ...",
          flush=True)

    X = np.memmap(PROC / "h67_stack.dat", dtype=np.float32, mode="w+", shape=(n, len(names)))
    for j in range(len(names)):
        X[:, j] = np.load(tmp / f"col_{j:03d}.npy", mmap_mode="r")
        (tmp / f"col_{j:03d}.npy").unlink()
    X.flush()
    del X
    design = Design(names=names, X=np.memmap(PROC / "h67_stack.dat", dtype=np.float32,
                                             mode="r", shape=(n, len(names))),
                    footprint=footprint, fp_idx=fp_idx, provenance=prov)
    meta = save(design)
    print(f"\nwrote {PROC / 'h67_stack.dat'}  shape={meta['shape']}  "
          f"{(PROC / 'h67_stack.dat').stat().st_size / 1e9:.2f} GB")
    print(f"layers: {', '.join(names)}")
    print(f"elapsed {time.time() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

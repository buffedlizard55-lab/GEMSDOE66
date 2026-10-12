#!/usr/bin/env python3
"""Stream the 19 official feature bands into a float32 memmap for fast strip reads."""
from __future__ import annotations

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
OFFICIAL_BANDS = ["det_elev", "det_elev_slope", "iso_grav_anom", "iso_grav_anom_slope",
                  "iso_grav_anom_hg", "iso_grav_anom_vg", "mag_anom", "rtp", "tmi",
                  "tmi_hg", "tmi_vg", "tc", "geod_2ndinv", "geod_shearrate",
                  "geod_dilaterate", "depth_to_base_surf", "cond_surf",
                  "deq_n100a15", "ieq_n100a15"]

def official_feature_names():
    with rasterio.open(ROOT / "data" / "training_features.tif") as s:
        return [str(x).split(" - ")[0] for x in s.descriptions]

H, W = 3730, 3292


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    t0 = time.time()
    out = ROOT / "data" / "derived" / "official_bands.f32"
    meta = ROOT / "data" / "derived" / "official_bands.json"
    src_path = ROOT / "data" / "training_features.tif"
    all_names = official_feature_names()
    order = [all_names.index(n) + 1 for n in OFFICIAL_BANDS]
    mm = np.memmap(out, dtype="float32", mode="w+", shape=(len(OFFICIAL_BANDS), H, W))
    with rasterio.open(src_path) as src:
        for j, bi in enumerate(order):
            v = src.read(bi).astype(np.float32)
            bad = (~np.isfinite(v)) | (v < -1e30)
            v[bad] = np.nan
            fin = ~bad
            m = float(np.median(v[fin])) if fin.any() else 0.0
            v[bad] = m
            mm[j] = v
            del v, bad, fin
            mm.flush()
            gc.collect()
            print(f"[{time.time()-t0:6.1f}s] band {OFFICIAL_BANDS[j]}", flush=True)
    mm.flush()
    del mm
    meta.write_text(json.dumps({
        "bands": OFFICIAL_BANDS,
        "shape": [len(OFFICIAL_BANDS), H, W],
        "dtype": "float32",
        "source": str(src_path.relative_to(ROOT)),
        "source_sha256": sha256_file(src_path),
        "file": str(out.relative_to(ROOT)),
        "sha256": sha256_file(out),
        "imputation": "non-finite / sentinel cells replaced by the band's in-footprint median",
    }, indent=1))
    print("done", round(time.time() - t0, 1), "s")
    return 0


if __name__ == "__main__":
    sys.exit(main())

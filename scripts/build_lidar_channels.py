#!/usr/bin/env python3
"""Build the LIDAR-01 channel stack and cache it as an on-disk float32 memmap.

Memory note: the grid is 3730 x 3292 = 12.28 M cells, so one float32 channel is ~49 MB
and the full stack is ~1.8 GB.  Channels are therefore streamed one at a time into a
memmap and the in-RAM copy is released immediately; peak RSS stays well under 1 GB.

Outputs:
  data/derived/lidar_lane_channels.f32   (nchan, 3730, 3292) float32 memmap
  data/derived/lidar_lane_channels.json  channel names, scale disclosure, input sha256
"""
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

from gems66.lidar_channels import (  # noqa: E402
    LIDAR_BANDS, dequantise, dequantise_topo, multiscale_line_fields,
    orientation_coherence, slope_aware_scarp_template,
)

H, W = 3730, 3292
RAW_LIDAR = ("ex_max", "ex_mean", "step_max", "lapneg_max", "lappos_max", "downface_max",
             "upface_max", "cross_max", "relief", "coh100", "strike", "valid")
TEMPLATE_OUT = ("template_antislope", "template_veto", "template_net",
                "template_net_coh", "snr_amp", "antislope_ratio")
MULTI_OUT = ("frangi_max", "frangi_scale", "steger_line", "steger_frac300")
TOPO_RAW = ("slope_p90", "slope_max", "steep_frac", "slope_std", "relief_local",
            "curv_prof_absmax", "aspect_coherence", "hs_lineament", "dem_mean")


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    t0 = time.time()
    log = lambda m: print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)
    data = ROOT / "data"
    lidar_p = data / "external" / "lidar_scarp_features_u8.tif"
    topo_p = data / "topo_10m_derived_100m_u8.tif"
    topo_m = data / "topo_10m_derived_100m_u8.manifest.json"
    out_dir = data / "derived"
    out_dir.mkdir(parents=True, exist_ok=True)

    names: list[str] = (
        [f"lid_{n}" for n in RAW_LIDAR]
        + ["lidar_cover"]
        + list(TEMPLATE_OUT)
        + [f"net_{k}" for k in MULTI_OUT]
        + [f"amp_{k}" for k in MULTI_OUT]
        + ["coh_recomputed"]
        + [f"topo_{n}" for n in TOPO_RAW]
    )
    mm_path = out_dir / "lidar_lane_channels.f32"
    mm = np.memmap(mm_path, dtype="float32", mode="w+", shape=(len(names), H, W))
    idx = {n: i for i, n in enumerate(names)}
    put = lambda n, a: mm.__setitem__(idx[n], np.nan_to_num(a, nan=0.0).astype(np.float32, copy=False))

    log(f"memmap allocated: {len(names)} channels")

    with rasterio.open(lidar_p) as src:
        raw = src.read()  # (12, H, W) uint8, ~148 MB
    stack: dict[str, np.ndarray] = {}
    for i, name in enumerate(LIDAR_BANDS):
        if name in ("upface_max", "downface_max", "cross_max", "step_max", "coh100"):
            stack[name] = dequantise(raw[i], name)
    del raw
    gc.collect()
    log("dequantised template-forming lidar bands")

    tmpl = slope_aware_scarp_template(stack)
    for k in TEMPLATE_OUT:
        put(k, tmpl[k])
    del tmpl
    gc.collect()
    log("slope-aware scarplet template written")

    # raw lidar bands (physical units), one at a time
    with rasterio.open(lidar_p) as src:
        for i, name in enumerate(LIDAR_BANDS):
            v = dequantise(src.read(i + 1), name)
            if name == "valid":
                put("lidar_cover", np.isfinite(v).astype(np.float32))
            put(f"lid_{name}", v)
            del v
            gc.collect()
    del stack
    gc.collect()
    log("raw lidar bands written")

    for tag, chan in (("net", "template_net"), ("amp", "snr_amp")):
        f = np.array(mm[idx[chan]], dtype=np.float32)
        got = multiscale_line_fields(f)
        for k in MULTI_OUT:
            put(f"{tag}_{k}", got[k])
        del got, f
        gc.collect()
        log(f"multiscale Steger/Frangi on {chan} written")

    put("coh_recomputed", orientation_coherence(
        np.array(mm[idx["snr_amp"]], dtype=np.float32), 1.0))
    gc.collect()
    log("structure-tensor coherence written")

    spec = json.loads(Path(topo_m).read_text())
    with rasterio.open(topo_p) as src:
        for b in spec["bands"]:
            v = dequantise_topo(src.read(b["index"]), b["lo"], b["hi"])
            put(f"topo_{b['band_name']}", v)
            del v
            gc.collect()
    log("10 m-derived topo bands written")

    mm.flush()
    del mm
    gc.collect()

    receipt = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "inputs": {p.name: {"sha256": sha256_file(p), "bytes": p.stat().st_size}
                   for p in (lidar_p, topo_p, topo_m)},
        "output": {
            "file": str(Path(mm_path).relative_to(ROOT)),
            "sha256": sha256_file(mm_path),
            "bytes": mm_path.stat().st_size,
            "shape": [len(names), H, W],
            "dtype": "float32",
            "channels": names,
        },
        "scale_disclosure": (
            "Steger/Frangi evaluated at sigma = 1.0, 1.5, 2.0, 3.0, 4.0 x 100 m cells "
            "(100-400 m). The lane's requested 2-20 m native scales require the 1 m/2 m "
            "bare-earth DEM, which is not reachable from this environment; the cached "
            "100 m aggregate preserves per-cell extrema of 2 m descriptors but not "
            "sub-cell geometry, so the native-resolution operator is NOT measured here."
        ),
        "elapsed_s": round(time.time() - t0, 1),
    }
    (out_dir / "lidar_lane_channels.json").write_text(json.dumps(receipt, indent=1))
    print(json.dumps({k: v for k, v in receipt.items() if k != "output"}, indent=1))
    print("n_channels:", len(names))
    return 0


if __name__ == "__main__":
    sys.exit(main())

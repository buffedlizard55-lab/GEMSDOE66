"""Decoder for an owner-described 2 m LiDAR stack; provenance is unverified here.

The legacy band names, quantization rule, work resolution, tile totals, caveats, and
physical-unit table below mirror an owner-supplied sidecar description referenced by
the historical manifest. The raster and sidecar are not present in this checkout, and
the manifest does not authenticate organizer origin, tile completeness, or the full
processing lineage. A future use must acquire authorized inputs, preserve hashes, and
re-verify the sidecar against the source workflow before interpreting any channel.

Inverse-quantizing a byte band only recovers a value under the stated quantization
assumption; it does not turn a proxy into a measured scarp attribute. In particular,
Scarplet amplitude/SNR/morphologic-age outputs require the actual template method and
cannot be inferred from a slope ratio or robust z-score.

Owner-described band definitions (not independently verified in this checkout):
  ex_max       max 2 m slope excess over 30 m regional slope                    [m/m]
  ex_mean      mean slope excess                                                [m/m]
  step_max     max difference between 10 m and 50 m slope scales                [m/m]
  lapneg_max   max crest convexity response                                     [1/m]
  lappos_max   max base concavity response                                      [1/m]
  downface_max / upface_max / cross_max  directional band-passed gradients     [m/m]
  relief       local elevation range                                            [m]
  coh100       structure-tensor orientation coherence at 100 m                  [-]
  strike       dominant scarp-strike proxy                                     [deg]
  valid        valid-LiDAR sample fraction per cell                             [-]

``read_bands`` requires the adjacent sidecar at runtime and must fail closed when it
is absent. No data download or full-footprint processing is performed by this module.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio

#: stack band order, 1-based raster band index -> name (sidecar "bands" list)
BANDS = ("ex_max", "ex_mean", "step_max", "lapneg_max", "lappos_max", "downface_max",
         "upface_max", "cross_max", "relief", "coh100", "strike", "valid")


@dataclass(frozen=True)
class Quant:
    xmax: float
    kind: str          # "sqrt" | "linear"

    def decode(self, q: np.ndarray) -> np.ndarray:
        """Inverse of ``q = 1 + round(254 * t(clip(x/xmax,0,1)))``; ``q == 0`` -> NaN."""
        q = np.asarray(q, np.float32)
        out = np.full(q.shape, np.nan, np.float32)
        ok = q > 0
        t = (q[ok] - 1.0) / 254.0
        r = t * t if self.kind == "sqrt" else t          # r = clip(x/xmax, 0, 1)
        out[ok] = (self.xmax * r).astype(np.float32)
        return out


def sidecar_for(tif: Path) -> Path:
    """The build workflow published the band spec next to the raster as ``<stem>.json``
    (here ``lidar_scarp_features.json``, i.e. the raster name minus the ``_u8`` suffix)."""
    tif = Path(tif)
    for cand in (tif.with_suffix(".json"), tif.parent / (tif.stem.replace("_u8", "") + ".json")):
        if cand.exists():
            return cand
    raise FileNotFoundError(f"no band sidecar next to {tif}")


def load_quant(path: Path) -> dict[str, Quant]:
    """Read the pinned sidecar; refuse to run if a band is missing an entry."""
    path = Path(path)
    spec = json.loads(sidecar_for(path).read_text())
    q = {k: Quant(float(v[0]), str(v[1])) for k, v in spec["quantisation"].items()}
    missing = [b for b in BANDS if b not in q]
    if missing:
        raise KeyError(f"sidecar has no quantisation entry for {missing}")
    return q


def read_bands(tif: Path, names: tuple[str, ...] = BANDS) -> dict[str, np.ndarray]:
    """Decode the selected bands of the stack to physical units (float32, NaN off-LiDAR)."""
    tif = Path(tif)
    quant = load_quant(sidecar_for(tif))
    out: dict[str, np.ndarray] = {}
    with rasterio.open(tif) as ds:
        idx = {n: i + 1 for i, n in enumerate(ds.descriptions or ())}
        unknown = [n for n in names if n not in idx]
        if unknown:
            raise KeyError(f"bands {unknown} not in raster descriptions {sorted(idx)}")
        for n in names:
            out[n] = quant[n].decode(ds.read(idx[n]))
    return out


def topo_band(tif: Path, name: str) -> np.ndarray:
    """10 m-derived topo stack (uint8 percentile, band names in the raster metadata).

    Used only for two dimensionless context terms (local relief and slope); no physical
    claim is attached to it, so it is returned as ``u8/255``.
    """
    with rasterio.open(tif) as ds:
        i = (ds.descriptions or ()).index(name) + 1
        a = ds.read(i).astype(np.float32) / 255.0
    return a

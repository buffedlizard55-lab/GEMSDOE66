"""Physical decode of the owner-pinned 2 m LiDAR scarp stack (band semantics, units).

Authoritative band definitions are **not** guessed here: they are read verbatim from
``data/external/lidar_scarp_features.json``, which is the sidecar the build workflow
published next to the raster
(https://github.com/buffedlizard55-lab/GEMSDOE24/blob/main/data/external/lidar_scarp_features.json;
workflow run https://github.com/buffedlizard55-lab/7GEMSDOE/actions/runs/36266555805).

The sidecar states, verbatim:

    "quantisation_rule": "q = 1 + round(254 * t(clip(x/xmax,0,1))), t in {sqrt, linear}; 0 = no lidar"
    "work_resolution_m": 2.0, "tiles_total": 716, "tile_status": {"ok": 706, "failed": 10}
    "caveats": ["uncalibrated terrain descriptors, not fault detections",
                "roads, channels, terrace risers, paleo-shorelines, landslides and mines also create steps"]

The second caveat is the exact failure mode this lane targets (see ``cultural66``).
Every prior LiDAR arm in this family consumed the *quantised* bands as dimensionless
weights (``u8 / 255`` -- e.g. ``GEMSDOE32/src/gems32/h33.py:153``); none decoded them
back to metres / (m/m) / (1/m). Decoding is what makes an SNR and a relative-age index
well defined, so it is done here and nowhere else in the family.

Units per band (from the sidecar ``channels_2m`` table, xmax per ``quantisation``):
  ex_max      max 2 m slope in excess of the 30 m regional slope            [m/m]  xmax 1.5, sqrt
  ex_mean     mean slope excess (short-wavelength steepness)                 [m/m]  xmax 0.3, sqrt
  step_max    max (10 m-scale slope - 50 m-scale slope)                      [m/m]  xmax 1.0, sqrt
  lapneg_max  max crest convexity -LoG(6 m) of the 50 m band-passed surface  [1/m]  xmax 0.05, sqrt
  lappos_max  max base concavity +LoG(6 m) of the 50 m band-passed surface   [1/m]  xmax 0.05, sqrt
  downface_max max band-passed step gradient along the regional upslope dir  [m/m]  xmax 1.0, sqrt
  upface_max  max band-passed step gradient against the regional slope       [m/m]  xmax 1.0, sqrt
  cross_max   max band-passed gradient across the regional slope             [m/m]  xmax 1.0, sqrt
  relief      local relief (zmax-zmin over the cell)                         [m]    xmax 300, sqrt
  coh100      structure-tensor orientation coherence at 100 m               [-]    xmax 1, linear
  strike      dominant scarp strike                                          [deg]  xmax 180, linear
  valid       fraction of valid lidar samples in the cell                    [-]    xmax 1, linear
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

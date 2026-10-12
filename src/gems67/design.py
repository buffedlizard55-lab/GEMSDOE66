"""On-disk design matrix for the H67 lane.

``scripts/h67_build_stack.py`` streams every layer from :mod:`gems67.stack` into one float32
memmap over the official footprint cells only (5,167,373 x n_features).  Keeping it on disk is
not an optimisation: the resident form is ~3 GB and this sandbox has 3.9 GB total.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
PROC = ROOT / "data" / "processed"
SHAPE_HW = (3730, 3292)


@dataclass
class Design:
    names: list[str]
    X: np.ndarray                      # (n_footprint, n_features) float32 memmap
    footprint: np.ndarray              # (H, W) bool
    fp_idx: np.ndarray                 # flat indices of footprint cells
    provenance: dict = field(default_factory=dict)

    @property
    def n(self) -> int:
        return int(self.X.shape[0])

    def col(self, name: str) -> np.ndarray:
        return self.X[:, self.names.index(name)]

    def to_grid(self, values: np.ndarray, fill=np.nan) -> np.ndarray:
        """Scatter a per-footprint vector back onto the full official grid."""
        out = np.full(SHAPE_HW, fill, dtype=np.float32)
        out.ravel()[self.fp_idx] = np.asarray(values, dtype=np.float32)
        return out

    def submatrix(self, names) -> np.ndarray:
        cols = [self.names.index(n) for n in names]
        return self.X[:, cols]


def save(design: Design, path: Path = PROC) -> dict:
    path.mkdir(parents=True, exist_ok=True)
    meta = {"names": design.names, "provenance": design.provenance,
            "shape": list(design.X.shape), "grid_shape": list(SHAPE_HW),
            "n_footprint": int(design.footprint.sum())}
    (path / "h67_stack_meta.json").write_text(json.dumps(meta, indent=1))
    np.save(path / "h67_footprint.npy", design.footprint)
    np.save(path / "h67_fp_idx.npy", design.fp_idx)
    return meta


def load(path: Path = PROC) -> Design:
    meta = json.loads((path / "h67_stack_meta.json").read_text())
    fp = np.load(path / "h67_footprint.npy")
    fp_idx = np.load(path / "h67_fp_idx.npy")
    X = np.memmap(path / "h67_stack.dat", dtype=np.float32, mode="r+",
                  shape=tuple(meta["shape"]))
    return Design(names=list(meta["names"]), X=X, footprint=fp, fp_idx=fp_idx,
                  provenance=meta.get("provenance", {}))


#: Layers that read a fault INVENTORY (the given catalogue, the USGS QFDB traces, the SGMC state
#: geologic map, the GDR thermal-spring points).  They are excluded from the geophysics-only
#: recipe because a spatially blocked holdout withholds whole fault segments and buffers the
#: remaining inventory by 300 m, which turns any inventory-proximity layer into an ANTI-signal
#: for the withheld truth (measured: 0.0178 vs a 0.0707 random-placement null, while the
#: inventory-free stack scored 0.1790 on the same folds -- evidence/h67_holdout_C*.json and
#: evidence/h67_null_control.json).
INVENTORY_LAYERS = ("d_visible_catalogue_m", "d_sgmc_m", "d_sgmc_off_visible_m", "sgmc_fault",
                    "d_qfaults_m", "qfaults_centroid", "d_hot_spring_m", "hot_spring_40c")

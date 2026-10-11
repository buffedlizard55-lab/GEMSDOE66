#!/usr/bin/env python3
"""Population-matched off-catalogue instrument (H66 lane, reusable).

Estimand
--------
Pooled distance-weighted Tversky index (alpha=0.2, beta=0.8, 300 m triangular
kernel -- the official metric, page 967) of one candidate field against a
**proxy new-fault truth band**: USGS SGMC state-map fault pixels that lie
more than 300 m (3 px) from the competition's published catalogue, inside the
study-area footprint.  The competition's scored truth is a set of expert-mapped
faults absent from that catalogue, so this band is the closest locally
computable population match; it is a *proxy*, never an organiser label, and its
absolute DTI is never a leaderboard score.

Reported per candidate
----------------------
* ``n_dots``   -- positive finite pixels inside the footprint
* ``mass``     -- sum of the field inside the footprint (binary fields: = n_dots)
* ``t``/``f``  -- the official TP_w / FP_w on the band (FN_w = |G| - TP_w)
* ``dti``      -- the official pooled DTI on the band
* ``credit_per_dot`` -- TP_w / mass, i.e. the mean kernel credit bought by one
  unit of emitted mass.  This is the quantity the score ladder of
  ``60GEMSDOE/docs/research/why-02778-and-what-beats-it-2026-10-11.md`` shows is
  worth 2.78e-6 of leaderboard score per unit change at the current mass.
* ``credit_per_dot_on_catalogue`` -- the same number measured against the
  published catalogue, as a leakage/drift check (a field that only ever scores
  high here is reciting the catalogue).

Usage:  python scripts/instrument66.py [--json evidence/h66_offcat_instrument.json] RASTER...
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems57 import metric as M                      # noqa: E402

CAT_SEP_PX = 3.0          # 300 m from the published catalogue, the champion's own minimum
N_RANDOM = 5
SEED = 66991


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def load(p: Path) -> np.ndarray:
    with rasterio.open(p) as ds:
        a = ds.read(1).astype(np.float64)
    return a


def build_truth(dcat: np.ndarray, sgmc: np.ndarray) -> np.ndarray:
    return sgmc & (dcat > CAT_SEP_PX)


def score_field(field: np.ndarray, truth: np.ndarray, foot: np.ndarray,
                known: np.ndarray) -> dict:
    """Official metric terms for a soft/binary field against one truth band.

    ``known`` (the published catalogue) is masked out of prediction *and* truth,
    exactly as ``gems57.metric.dti_exact`` does with ``known=``.
    """
    r = M.dti_exact(field, truth, valid=foot, known=known)
    mass = float(np.where(foot & ~known, np.maximum(field, 0.0), 0.0).sum())
    n = int(((field > 0) & foot & ~known).sum())
    return dict(n_dots=n, mass=mass, t=r["tp"], f=r["fp"], fn=r["fn"],
                n_truth=r["n_truth"], dti=r["dti"],
                coverage=r["coverage"],
                credit_per_dot=(r["tp"] / mass) if mass > 0 else 0.0)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("rasters", nargs="+")
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    lab = load(ROOT / "data/bridge/labels.tif")
    foot = lab != -1
    cat = lab == 1
    dcat = ndi.distance_transform_edt(~cat).astype(np.float32)
    sgmc = load(ROOT / "data/external/sgmc_faults_100m.tif") > 0
    truth = build_truth(dcat, sgmc)
    truth &= foot
    rep = dict(schema_version=1, generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               instrument="pooled DTI (alpha 0.2, beta 0.8, 300 m triangular) against SGMC "
                          "state-map fault pixels > 300 m from the published catalogue, "
                          "footprint-restricted, catalogue cells excluded from prediction and truth",
               truth_source="data/external/sgmc_faults_100m.tif (USGS SGMC 100 m raster, in-repo)",
               truth_source_sha256=sha256(ROOT / "data/external/sgmc_faults_100m.tif"),
               catalogue_source_sha256=sha256(ROOT / "data/bridge/labels.tif"),
               cat_sep_px=CAT_SEP_PX, truth_pixels=int(truth.sum()),
               footprint_pixels=int(foot.sum()), candidates={})
    rng = np.random.default_rng(SEED)
    elig = foot & ~cat & (dcat > CAT_SEP_PX)
    ys, xs = np.nonzero(elig)
    for p in a.rasters:
        path = Path(p)
        if not path.is_absolute():
            path = ROOT / path
        f = load(path)
        if f.shape != foot.shape:
            rep["candidates"][str(p)] = {"error": f"shape {f.shape} != {foot.shape}"}
            continue
        rec = score_field(f, truth, foot, cat)
        # binary twin: the same mass as unit dots, for binary-vs-soft comparison
        thr = np.quantile(f[elig & (f > 0)], 0.0) if False else None
        rec["catalogue_side"] = score_field(np.where(cat, 0.0, f), cat & foot, foot,
                                            ~cat)
        rec["sha256"] = sha256(path)
        rep["candidates"][str(p)] = rec
        # mass-matched uniform random control
        n = max(rec["n_dots"], 1)
        rr = []
        for i in range(N_RANDOM):
            pick = rng.choice(len(ys), size=min(n, len(ys)), replace=False)
            rnd = np.zeros(foot.shape, np.float64)
            rnd[ys[pick], xs[pick]] = 1.0
            rr.append(score_field(rnd, truth, foot, cat))
        rec["random_mass_matched"] = dict(
            n=N_RANDOM, dti_mean=float(np.mean([x["dti"] for x in rr])),
            dti_sd=float(np.std([x["dti"] for x in rr])),
            credit_per_dot_mean=float(np.mean([x["credit_per_dot"] for x in rr])))
        rec["excess_credit_per_dot"] = rec["credit_per_dot"] - rec["random_mass_matched"]["credit_per_dot_mean"]
        print(f"{path.name:58s} n={rec['n_dots']:7d} dti={rec['dti']:.5f} "
              f"cpd={rec['credit_per_dot']:.4f} (rand {rec['random_mass_matched']['credit_per_dot_mean']:.4f}) "
              f"x{rec['credit_per_dot'] / max(rec['random_mass_matched']['credit_per_dot_mean'], 1e-9):.2f}")
    if a.json:
        out = ROOT / a.json
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rep, indent=2) + "\n")
        print("wrote", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

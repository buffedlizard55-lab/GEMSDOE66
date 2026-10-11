#!/usr/bin/env python3
"""H66-2 stratum measurement: where does the LiDAR lane's edge actually come from?

The H66-1 session measured one aggregate number on the off-catalogue proxy (SGMC
state-map faults >300 m from the published catalogue) and read it as "the lane's field
carries off-catalogue fault signal".  This script splits that single number into the two
sub-populations that behave differently, at matched mass, and adds the controls that
decide whether the edge is a *fault* signal or a *terrain* signal:

  basin stratum    eligible cells with 10 m slope_p90 below the eligible median
  upland stratum   the rest
  control          rank(10 m slope_p90) -- contains no LiDAR information at all
  incumbent        the live-scored 0.2778 champion raster, at its own mass and at ours

Estimand for every arm: pooled DTI (alpha .2, beta .8, 300 m triangular) and credit per
unit mass against the stratum's SGMC-off truth pixels.  Proxy truth, never a score.

Writes evidence/h66b_e2_strata.json.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from gems57 import metric as M                                    # noqa: E402
from gems66 import channels66 as C66                              # noqa: E402
from gems66.spec66 import topo_band                               # noqa: E402

CAT_SEP_PX = 3.0
NMS_PX = 2.8
N_MASS = 37_654          # the live-validated rung the champion occupies
SEED = 66301


def rd(rel: str) -> np.ndarray:
    with rasterio.open(ROOT / rel) as ds:
        return ds.read(1)


def pick(field: np.ndarray, n: int, mask: np.ndarray) -> np.ndarray:
    s = np.where(mask, field, 0.0).astype(np.float32)
    yy, xx = np.mgrid[-3:4, -3:4]
    fp = np.zeros((7, 7), bool)
    fp[:] = (yy * yy + xx * xx) <= (NMS_PX ** 2)
    mx = ndi.maximum_filter(s, footprint=fp, mode="constant", cval=0.0)
    pk = (s >= mx) & (s > 0) & mask
    ys, xs = np.nonzero(pk)
    if len(ys) > n:
        o = np.argsort(-s[ys, xs])[:n]
        ys, xs = ys[o], xs[o]
    out = np.zeros(field.shape, bool)
    out[ys, xs] = True
    return out


def score(dots: np.ndarray, truth: np.ndarray, foot, cat) -> dict:
    r = M.dti_exact(dots.astype(np.float64), truth, valid=foot, known=cat)
    n = int(dots.sum())
    return dict(n_dots=n, t=r["tp"], f=r["fp"], fn=r["fn"], n_truth=r["n_truth"],
                dti=r["dti"], coverage=r["coverage"],
                credit_per_dot=(r["tp"] / n) if n else 0.0)


def main() -> int:
    lab = rd("data/bridge/labels.tif").astype(np.float64)
    foot = lab != -1
    cat = lab == 1
    dcat = ndi.distance_transform_edt(~cat).astype(np.float32)
    sgmc = rd("data/external/sgmc_faults_100m.tif") > 0
    dom = foot & (dcat > CAT_SEP_PX)
    offcat = sgmc & foot & (dcat > CAT_SEP_PX)
    slope = topo_band("data/external/topo_10m_derived_100m_u8.tif", "slope_p90")
    med = float(np.median(slope[dom]))
    basin = dom & (slope < med)
    upland = dom & ~basin
    truth_b = offcat & (slope < med)
    truth_u = offcat & (slope >= med)
    fields = np.load(ROOT / "evidence/h66b_fields.npz")
    names = [n for n in fields.files if n != "dom"]
    champ = rd("registry/rasters/GEMSDOE32__h33-2-b2-zeros.tif") > 0

    rep = dict(generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               evidence_class="OFF-CATALOGUE-PROXY (stratum split; never a score)",
               instrument="pooled DTI (alpha .2, beta .8, 300 m triangular kernel) against USGS "
                          "SGMC fault pixels >300 m from the published catalogue, within one stratum",
               slope_split_rule="eligible (LiDAR-reachable, >=300 m off catalogue) cells split at the "
                                "median 10 m slope_p90; median=%.6f" % med,
               strata=dict(basin=dict(cells=int(basin.sum()), truth_pixels=int(truth_b.sum())),
                           upland=dict(cells=int(upland.sum()), truth_pixels=int(truth_u.sum()))),
               budget=N_MASS, seed=SEED,
               baseline_correction=("IR-66-BASE-01: per-stratum random baselines are uniform draws "
                                    "inside the stratum. The 2026-10-11 first run's baselines were "
                                    "index-ordered corner cells and are superseded."),
               arms={})
    rng = np.random.default_rng(SEED)
    for tag, mask, truth in (("basin", basin, truth_b), ("upland", upland, truth_u)):
        rep["arms"][tag] = {}
        # Mass-matched random control inside the stratum.
        # IR-66-BASE-01 (fixed 2026-10-11): the first run drew the "random" control with
        # pick(np.ones(...)), whose argsort on a constant field returns cells in raster order --
        # i.e. the first N_MASS cells of the stratum (the top-left corner of the map), not a
        # random sample.  That inflated every ratio_over_stratum_random by ~13x.  Draw a true
        # uniform sample inside the stratum instead.
        idx = np.flatnonzero(mask.ravel())
        rnd = []
        for _ in range(3):
            sel = rng.choice(idx, size=int(N_MASS), replace=False)
            m = np.zeros(foot.shape, bool)
            m.ravel()[sel] = True
            rnd.append(score(m, truth, foot, cat))
        base = float(np.mean([x["credit_per_dot"] for x in rnd]))
        rep["arms"][tag]["random_mass_matched"] = dict(
            credit_per_dot_mean=base, credit_per_dot_sd=float(np.std([x["credit_per_dot"] for x in rnd])),
            dti_mean=float(np.mean([x["dti"] for x in rnd])), n=3)
        # controls: 10 m terrain steepness/relief, no LiDAR input
        controls = {"control_toposlope_p90": C66.robust_rank(slope, mask),
                    "control_topo_relief_local": C66.robust_rank(
                        topo_band("data/external/topo_10m_derived_100m_u8.tif", "relief_local"), mask)}
        # the incumbent: its own dots inside the stratum, and its mass-matched subset at N_MASS
        rec_ch = score(champ & mask, truth, foot, cat)
        rec_ch["note"] = ("the incumbent's own dots inside this stratum (its natural mass), "
                          "not a re-emission")
        rep["arms"][tag]["champion_h33_2_b2_own_dots"] = rec_ch
        if int((champ & mask).sum()) >= N_MASS:
            rep["arms"][tag]["champion_h33_2_b2_mass_matched"] = score(
                pick(champ.astype(np.float32), N_MASS, mask), truth, foot, cat)
        for name in names:
            f = np.nan_to_num(fields[name])
            rec = score(pick(f, N_MASS, mask), truth, foot, cat)
            rec["ratio_over_stratum_random"] = rec["credit_per_dot"] / max(base, 1e-12)
            rep["arms"][tag][name] = rec
        for name, f in controls.items():
            f = np.where(np.isfinite(f), f, 0.0)
            rec = score(pick(f.astype(np.float32), N_MASS, mask), truth, foot, cat)
            rec["ratio_over_stratum_random"] = rec["credit_per_dot"] / max(base, 1e-12)
            rep["arms"][tag][name] = rec
        rep["arms"][tag]["champion_h33_2_b2_own_dots"]["ratio_over_stratum_random"] = \
            rec_ch["credit_per_dot"] / max(base, 1e-12)
        print(f"[{tag}] K={int(truth.sum())} cells={int(mask.sum())} random_cpd={base:.5f}", flush=True)
        for k, v in sorted(rep["arms"][tag].items(),
                           key=lambda kv: -kv[1].get("ratio_over_stratum_random", 0)):
            if "credit_per_dot" in v:
                print(f"   {k:34s} n={v['n_dots']:7d} cpd={v['credit_per_dot']:.5f} "
                      f"x{v.get('ratio_over_stratum_random', 0):6.2f} dti={v['dti']:.5f}", flush=True)
    (ROOT / "evidence/h66b_e2_strata.json").write_text(json.dumps(rep, indent=2) + "\n")
    print("wrote evidence/h66b_e2_strata.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

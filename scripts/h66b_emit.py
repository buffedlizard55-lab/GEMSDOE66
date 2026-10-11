#!/usr/bin/env python3
"""H66-2 artifact builder: emit, validate, measure and receipt the lane's candidate.

What is emitted
---------------
ONE GeoTIFF: 37,654 unit dots (the live-validated rung's mass) placed on the top of the
H66-2 field inside the LiDAR-covered, >=300 m off-catalogue eligibility domain, thinned at
2.8 px, with **no cultural veto** (H66-1 measured that veto as a clean negative: -1.0e-5 DTI,
95 % CI crossing zero).  Encoding: single-band float32, EPSG:32611, 100 m, identical
transform/bounds to ``sample_submission.tif``, every cell finite, all values in [0,1],
zero outside the footprint -- the encoding the live-scored 0.2778 artifact already used and
the portal already accepted, and the reason the earlier ``-nan`` sibling could be rejected
with "Predicted values must be in range [0, 1]".

Field: H66-2 concordance = ( rank(step_max) * rank(1 - facing) * rank(sharp) ) ** (1/3),
built only from the pinned 2 m LiDAR scarp stack (data/external/lidar_scarp_features_u8.tif,
sidecar-verified quantisation) inside the LiDAR-covered footprint.  No label, no catalogue
and no external product enters the field.

Receipts: evidence/h66b_emission.json (validator + instrument + sweep),
docs/downloads/<name>.tif + .zip + .json (written by the shared fail-closed writer).
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
from gems57 import metric as M                                       # noqa: E402
from gems57 import submission_writer as SW                           # noqa: E402
from gems66 import channels66 as C66                                 # noqa: E402
from gems66.spec66 import topo_band                                  # noqa: E402

EXT = ROOT / "data" / "external"
CAT_SEP_PX = 3.0
NMS_PX = 2.8
BUDGET = 37_654
NAME = "GEMSDOE66-H66-2-LIDAR-SCARP-CONCORDANCE-37654"
NOTE = ("H66-2 lidar scarp concordance (step x antislope x sharpness), 37654 dots >=300 m off "
        "catalogue; proxy-validated field, no organizer score")
SWEEP = (20_000, 37_654, 60_000)


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


def score(dots: np.ndarray, truth, foot, cat) -> dict:
    r = M.dti_exact(dots.astype(np.float64), truth, valid=foot, known=cat)
    n = int(dots.sum())
    return dict(n_dots=n, t=r["tp"], f=r["fp"], fn=r["fn"], n_truth=r["n_truth"], dti=r["dti"],
                coverage=r["coverage"], credit_per_dot=(r["tp"] / n) if n else 0.0)


def main() -> int:
    t0 = time.time()
    lab = rd("data/bridge/labels.tif").astype(np.float64)
    foot, cat = lab != -1, lab == 1
    dcat = ndi.distance_transform_edt(~cat).astype(np.float32)
    sgmc = rd("data/external/sgmc_faults_100m.tif") > 0
    dom = foot & (dcat > CAT_SEP_PX)
    truth = sgmc & foot & (dcat > CAT_SEP_PX)
    slope = topo_band(str(EXT / "topo_10m_derived_100m_u8.tif"), "slope_p90")
    med = float(np.median(slope[dom]))
    fields = np.load(ROOT / "evidence/h66b_fields.npz")
    field = np.nan_to_num(fields["concordance_step_face"])
    dots = pick(field, BUDGET, dom)
    pred = np.zeros(lab.shape, np.float32)
    pred[dots] = 1.0
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    tag = f"gems66-h66-2-concordance-scarp-{int(dots.sum())}-{stamp}"
    path = ROOT / "docs" / "downloads" / f"{tag}-allfinite.tif"
    rec = SW.write_submission(path, pred, ROOT / "data/bridge/sample_submission.tif", foot,
                              note=NOTE, name=NAME, catalogue=cat,
                              metadata=dict(lane="H66-2 native-resolution lidar scarp channels",
                                            field="(rank(step_max)*rank(1-facing)*rank(sharp))**(1/3)",
                                            eligibility="lidar-covered, >=300 m off catalogue, no veto",
                                            nms_px=NMS_PX, budget=BUDGET))
    val = rec["validator"]
    assert val["all_checks_passed"] and rec["template_report"]["ok"], "writer receipt failed"
    out = dict(generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               tag=tag, seconds=round(time.time() - t0, 1), name=NAME, note=NOTE,
               note_chars=len(NOTE), writer_receipt=rec)
    # instrument (global + strata) for the emitted dots
    strata = {}
    for tname, mask, truth_s in (("all_off_catalogue", dom, truth),
                                 ("basin", dom & (slope < med), truth & (slope < med)),
                                 ("upland", dom & (slope >= med), truth & (slope >= med))):
        s = score(dots & mask if tname != "all_off_catalogue" else dots, truth_s, foot, cat)
        strata[tname] = s
    out["instrument"] = dict(
        definition="pooled DTI (alpha .2, beta .8, 300 m triangular) vs USGS SGMC state-map faults "
                   ">300 m from the published catalogue; PROXY truth, never a score",
        global_off_catalogue=strata["all_off_catalogue"],
        basin=strata["basin"], upland=strata["upland"], slope_split_median=med)
    out["budget_sweep"] = {}
    for n in SWEEP:
        d = pick(field, n, dom)
        out["budget_sweep"][n] = score(d, truth, foot, cat)
    # leakage canary against catalogue proximity (same estimator H66-1 used)
    from sklearn.metrics import roc_auc_score
    ch_cover = C66.build_channels(EXT, foot).covered          # the field's own domain
    near = (dcat <= 1.0) & ch_cover
    rng = np.random.default_rng(66203)
    yy, xx = np.nonzero(ch_cover)
    keep = rng.random(len(yy)) < 0.25
    ys, xs = yy[keep], xx[keep]
    auc = float(roc_auc_score(near[ys, xs].astype(int), field[ys, xs]))
    out["leakage_canary"] = dict(
        domain="LiDAR-covered footprint cells (the field's own domain)",
        label="cell within 100 m of a mapped catalogue fault (positive) vs the rest",
        auc_field=round(auc, 4), n_eval=int(keep.sum()), n_positive=int(near[ys, xs].sum()),
        emitted_dots_on_catalogue=int((dots & cat).sum()),
        dots_within_300m_of_catalogue=int((dots & (dcat <= CAT_SEP_PX)).sum()),
        verdict="ok" if max(auc, 1 - auc) <= 0.90 else "LEAKAGE-SUSPECT")
    # the portal rejection mode (IR-57-NAN-02): explicit byte-level check of the on-disk file
    with rasterio.open(ROOT / "docs" / "downloads" / f"{tag}-allfinite.tif") as ds:
        a = ds.read(1)
    out["portal_range_check"] = dict(
        file=f"{tag}-allfinite.tif", dtype=str(a.dtype), n_nan=int(np.isnan(a).sum()),
        n_inf=int(np.isinf(a).sum()), vmin=float(a.min()), vmax=float(a.max()),
        all_values_finite=bool(np.isfinite(a).all()),
        all_values_in_0_1=bool((a >= 0).all() and (a <= 1).all()),
        note="the earlier portal error 'Predicted values must be in range [0, 1]' cannot be raised by "
             "this file: it contains no NaN and no value outside [0,1] anywhere on the grid")
    (ROOT / "evidence" / "h66b_emission.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps({k: out[k] for k in ("tag", "seconds")}, indent=1))
    print("writer: all_checks_passed =", val["all_checks_passed"], "| template ok =", rec["template_report"]["ok"])
    print("instrument(global):", {k: round(v, 5) if isinstance(v, float) else v
                                  for k, v in strata["all_off_catalogue"].items()})
    print("instrument(basin):", {k: round(v, 5) if isinstance(v, float) else v
                                 for k, v in strata["basin"].items()})
    print("instrument(upland):", {k: round(v, 5) if isinstance(v, float) else v
                                  for k, v in strata["upland"].items()})
    print("sha256:", rec["sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

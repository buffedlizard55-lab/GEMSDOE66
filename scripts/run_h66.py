#!/usr/bin/env python3
"""H66-1 runner: native-resolution LiDAR scarplet channels, cultural veto, and the gate.

Stages (each writes its own evidence JSON, so a partial run is still auditable):

  s0  verify every input byte against the pinned sha256 in ``registry/data_manifest.json``
  s1  build the physical channels + the cultural index, and run the leakage canary
  s2  E1: population-matched off-catalogue instrument -- credit/dot and pooled DTI for
      {scarplet field}, {scarplet field - cultural veto}, {mass-matched random}, {distance-only}
  s3  retrain under spatial CV (logistic, 4 spatial blocks) with / without the cultural feature
  s4  E2: the registered pooled hide-and-recover holdout (gems57), plus the
      "not confined to range fronts" stratification
  s5  E3: the emission (2.8-px NMS, budget sweep) -> normalized float32 GeoTIFF + zip + receipts

Usage:  python scripts/run_h66.py s0 s1 s2 ...      (default: all)
"""
from __future__ import annotations

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

from gems57 import grid as G57                                   # noqa: E402
from gems57 import holdout as H57                                # noqa: E402
from gems57 import metric as M57                                 # noqa: E402
from gems66 import channels66 as C66                             # noqa: E402
from gems66.spec66 import BANDS                                   # noqa: E402

DATA = ROOT / "data"
EXT = DATA / "external"
EV = ROOT / "evidence"
EV.mkdir(exist_ok=True)
RNG = np.random.default_rng(661011)
LID_MIN = 0.5            # "lidar-covered" cell: >= 50 % valid 2 m samples in the 100 m cell
CAT_SEP_PX = 3.0         # emission must sit >= 300 m from the published catalogue (champion's own minimum)
NMS_PX = 2.8             # family thinning convention (r7-nms3 / H66-1 of the chi lane)
BUDGETS = (12_000, 24_000, 37_654, 60_000)   # 37,654 = mass-matched to the live-scored champion
N_RANDOM = 5


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ----------------------------------------------------------------------------- s0
def s0_verify(st=None) -> dict:
    pins = json.loads((ROOT / "registry" / "data_manifest.json").read_text())
    # keyed by BOTH the manifest dest and the basename, because the bridge re-files the
    # core rasters under data/bridge/ while the manifest records their original dest.
    want = {}
    for f in pins["files"]:
        if f.get("dest"):
            want[f["dest"]] = f["sha256"]
            want[Path(f["dest"]).name] = f["sha256"]
    out = {"generated_utc": now(), "checked": {}, "missing": [], "mismatch": []}
    local = {}
    for p in list(DATA.rglob("*.tif")) + list(DATA.rglob("*.json")):
        local[str(p.relative_to(DATA))] = p
    for dest, path in sorted(local.items()):
        exp = want.get(dest) or want.get(path.name)
        got = sha256(path)
        rec = {"sha256": got, "pinned": exp, "match": (exp == got) if exp else None,
               "bytes": path.stat().st_size}
        if exp is None:                                  # second-tier pins: sibling receipts
            for side in sorted(DATA.rglob("*.json")):
                try:
                    blob = side.read_text()
                except UnicodeDecodeError:
                    continue
                if got in blob:
                    rec.update(match=True, pinned=f"sha256 found verbatim in {side.relative_to(DATA)}")
                    break
        out["checked"][dest] = rec
        if exp is None:
            rec["note"] = "not in the pinned manifest"
        elif exp != got:
            out["mismatch"].append(dest)
    out["ok"] = not out["mismatch"]
    (EV / "h66_inputs.json").write_text(json.dumps(out, indent=2) + "\n")
    assert out["ok"], f"hash mismatch: {out['mismatch']}"
    return out


# ----------------------------------------------------------------------------- shared state
def load_state():
    grid = G57.load_grid(DATA / "bridge")
    with rasterio.open(EXT / "derived_sgmc_faults_100m_u8.tif") as ds:
        sgmc = ds.read(1) > 0
    dcat = ndi.distance_transform_edt(~grid.catalogue).astype(np.float32)
    dom = grid.footprint.copy()
    st = dict(grid=grid, sgmc=sgmc, dcat=dcat, dom=dom)
    return st


def lidar_domain(st) -> np.ndarray:
    """Footprint cells with >=50 % valid lidar samples (sidecar band ``valid``)."""
    with rasterio.open(EXT / "lidar_scarp_features_u8.tif") as ds:
        v = ds.read(BANDS.index("valid") + 1).astype(np.float32)
    val = v > 0
    lid = np.where(val, (v - 1) / 254.0, 0.0)          # 'valid' is linear, xmax 1.0
    return st["dom"] & (lid >= LID_MIN)


# ----------------------------------------------------------------------------- s1
def s1_channels(st) -> dict:
    dom = lidar_domain(st)
    ch = C66.build_channels(EXT, dom, lid_min=LID_MIN)
    cul = C66.cultural_mask(ch, dom, EXT)
    score, info = C66.scarplet_score(ch, cul, dom)
    st.update(ch=ch, cul=cul)
    np.savez_compressed(
        EV / "h66_fields.npz",
        amp_snr=np.nan_to_num(ch.amp_snr), snr=np.nan_to_num(ch.snr), frac=np.nan_to_num(ch.frac),
        coh100=np.nan_to_num(ch.coh_cell), rel_age=np.nan_to_num(ch.rel_age), facing=np.nan_to_num(ch.facing),
        sharp=np.nan_to_num(ch.sharp), height_m=np.nan_to_num(ch.height_m), relief_m=np.nan_to_num(ch.relief_m),
        strike=np.nan_to_num(ch.strike),
        score=score, score_unvetoed=np.where(dom, C66.robust_rank(np.nan_to_num(ch.amp_snr), dom) * 0.35
                                              + C66.robust_rank(np.nan_to_num(ch.frac), dom) * 0.25
                                              + C66.robust_rank(np.nan_to_num(ch.coh_cell), dom) * 0.25
                                              + C66.robust_rank(np.nan_to_num(ch.rel_age), dom) * 0.15, 0.0),
        cultural=cul.index, veto=cul.mask, dom=dom)
    # leakage canary: each channel alone, AUC against catalogue proximity (100 m) within the
    # lidar-covered footprint.  >0.90 would mean the channel is the label in disguise.
    near_cat = (st["dcat"] <= 1.0) & dom
    feats = {name: np.nan_to_num(v) for name, v in
             dict(amp_snr=ch.amp_snr, snr=ch.snr, frac=ch.frac, coh100=ch.coh_cell,
                  rel_age=ch.rel_age, facing=ch.facing, sharp=ch.sharp, step=ch.step,
                  height_m=ch.height_m, relief_m=ch.relief_m, cultural=cul.index).items()}
    from sklearn.metrics import roc_auc_score
    sub = dom.copy()
    yy, xx = np.nonzero(sub)
    keep = RNG.random(sub.sum()) < 0.25               # 1.3 M cells is plenty for an AUC
    ys, xs = yy[keep], xx[keep]
    lab = near_cat[ys, xs].astype(int)
    canary = {}
    for name, arr in feats.items():
        v = arr[ys, xs]
        a = float(roc_auc_score(lab, v))
        canary[name] = dict(auc=round(a, 4), auc_reflected=round(max(a, 1 - a), 4),
                            verdict="LEAKAGE-SUSPECT" if max(a, 1 - a) > 0.90 else "ok")
    rep = dict(generated_utc=now(), evidence_class="HOLDOUT-DTI-instrument-audit",
               lidar_covered_cells=int(dom.sum()), lidar_fraction_of_footprint=round(float(dom.sum() / st['dom'].sum()), 4),
               positive_control=dict(name="distance-to-catalogue itself",
                                     auc=round(float(roc_auc_score(lab, -st["dcat"][ys, xs])), 4),
                                     note="deliberate positive control, not a lane input"),
               canary=canary, cultural=cul.diagnostics, score=info,
               n_label_pos=int(lab.sum()))
    (EV / "h66_e1_canary.json").write_text(json.dumps(rep, indent=2) + "\n")
    return rep


# ----------------------------------------------------------------------------- instruments
def instrument(st, dots: np.ndarray, truth: np.ndarray, dom: np.ndarray) -> dict:
    """Pooled DTI + credit/dot for a binary dot set, official formula via gems57."""
    p = dots & dom
    r = M57.dti_binary(p, truth & dom, valid=dom, known=st["grid"].catalogue)
    ktot = float(M57.kernel(ndi.distance_transform_edt(~(truth & dom))[p]).sum()) if p.any() else 0.0
    r["credit_per_dot"] = ktot / max(int(p.sum()), 1)
    r["n_dots"] = int(p.sum())
    r["on_visible_catalogue"] = int((p & st["grid"].catalogue).sum())
    return r


def block_bootstrap(st, arms: dict, candidate: str, ref: str, dom: np.ndarray,
                    draws: int = 1000, block: int = 200) -> dict:
    """Paired 20 km spatial-block bootstrap of DTI(candidate) - DTI(ref) on the same truth."""
    ny = (dom.shape[0] + block - 1) // block
    bid = np.repeat(np.arange(ny), block)[: dom.shape[0]][:, None] * ((dom.shape[1] + block - 1) // block) \
        + np.repeat(np.arange((dom.shape[1] + block - 1) // block), block)[: dom.shape[1]][None, :]
    out = {}
    per = {}
    for name, (dots, truth) in arms.items():
        d = M57.kernel(ndi.distance_transform_edt(~(dots & dom)))
        # per-block components
        terms = np.zeros((bid.max() + 1, 3))
        act = (truth & dom)
        yy, xx = np.nonzero(act)
        tp = d[yy, xx]
        np.add.at(terms, (bid[yy, xx], 0), tp)
        np.add.at(terms, (bid[yy, xx], 2), 1.0 - tp)
        pcells = dots & dom
        yg, xg = np.nonzero(pcells)
        kdot = M57.kernel(ndi.distance_transform_edt(~act)[yg, xg]) if len(yg) else np.zeros(0)
        np.add.at(terms, (bid[yg, xg], 1), 1.0 - kdot)
        per[name] = terms
    rng = np.random.default_rng(661207)
    nb = len(per[candidate])
    keep = np.any(np.stack([a.sum(1) for a in per.values()]) > 0, axis=0)
    idx = np.flatnonzero(keep)
    draws_idx = rng.integers(0, len(idx), size=(draws, len(idx)))
    dti = {}
    for name, terms in per.items():
        sel = terms[draws_idx].sum(axis=1)
        dti[name] = sel[:, 0] / (sel[:, 0] + M57.ALPHA * sel[:, 1] + M57.BETA * sel[:, 2] + M57.EPS)
    delta = dti[candidate] - dti[ref]
    out = dict(candidate=candidate, reference=ref, blocks=int(len(idx)), draws=draws,
               delta_dti_mean=float(delta.mean()),
               delta_dti_ci95=[float(np.quantile(delta, .025)), float(np.quantile(delta, .975))],
               p_positive=float((delta > 0).mean()))
    return out


def _offcat_truth(st, dom):
    return st["sgmc"] & dom & (st["dcat"] > CAT_SEP_PX)


def _pick(score: np.ndarray, elig: np.ndarray, n: int, rng=None) -> np.ndarray:
    """Top-n of ``score`` inside ``elig`` with maximum-filter NMS at NMS_PX."""
    s = np.where(elig, score, 0.0).astype(np.float32)
    foot = np.zeros((7, 7), bool)
    yy, xx = np.mgrid[-3:4, -3:4]
    foot[:] = (yy * yy + xx * xx) <= (NMS_PX ** 2)
    mx = ndi.maximum_filter(s, footprint=foot, mode="constant", cval=0.0)
    peaks = (s >= mx) & (s > 0) & elig
    ys, xs = np.nonzero(peaks)
    if len(ys) == 0:
        return peaks
    if len(ys) > n:
        order = np.argsort(-s[ys, xs])[:n]
        ys, xs = ys[order], xs[order]
    out = np.zeros(score.shape, bool)
    out[ys, xs] = True
    return out


def _random_dots(dom: np.ndarray, elig: np.ndarray, n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    ys, xs = np.nonzero(elig)
    k = rng.choice(len(ys), size=min(n, len(ys)), replace=False)
    out = np.zeros(dom.shape, bool)
    out[ys[k], xs[k]] = True
    return out


# ----------------------------------------------------------------------------- s2
def s2_e1(st) -> dict:
    """E1 -- the population-matched, off-catalogue first test of the veto."""
    f = np.load(EV / "h66_fields.npz")
    score, unvet, veto, dom = f["score"], f["score_unvetoed"], f["veto"], f["dom"]
    elig = dom & (st["dcat"] > CAT_SEP_PX)
    truth = _offcat_truth(st, dom)
    rep = {"generated_utc": now(), "evidence_class": "HOLDOUT-DTI (population-matched instrument)",
           "instrument": "pooled DTI + credit/dot of a binary emission against USGS SGMC mapped "
                         "faults that lie >300 m from the competition catalogue, inside the "
                         "lidar-covered footprint, catalogue cells excluded from scoring (gems57)",
           "truth_pixels_off_catalogue": int(truth.sum()),
           "eligibility_cells": int(elig.sum()), "veto_cells": int((veto & elig).sum()),
           "budgets": {}}
    for N in BUDGETS:
        dots_v = _pick(score, elig, N)
        dots_u = _pick(unvet, elig, N)
        rec = {"vetoed": instrument(st, dots_v, truth, dom), "unvetoed": instrument(st, dots_u, truth, dom)}
        rr = [instrument(st, _random_dots(dom, elig, N, 7000 + 13 * i), truth, dom)["dti"] for i in range(N_RANDOM)]
        rec["random_mass_matched"] = dict(dti_mean=float(np.mean(rr)), dti_sd=float(np.std(rr)),
                                          n=len(rr), dots=N)
        arms = {"vetoed": (dots_v, truth), "unvetoed": (dots_u, truth)}
        rec["paired_bootstrap_veto_vs_unveto"] = block_bootstrap(
            st, dict(arms, **{"random": (_random_dots(dom, elig, N, 7001), truth)}), "vetoed", "unvetoed", dom)
        rec["union_overlap_pct"] = round(100.0 * float((dots_v & dots_u).sum()) / max(int(dots_u.sum()), 1), 2)
        rec["veto_removed_from_unvetoed"] = int((dots_u & veto).sum())
        rep["budgets"][N] = rec
    (EV / "h66_e1_offcat.json").write_text(json.dumps(rep, indent=2) + "\n")
    return rep


# ----------------------------------------------------------------------------- s3
def s3_retrain(st) -> dict:
    """Retrain under spatial CV: does the cultural index carry independent information?"""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    f = np.load(EV / "h66_fields.npz")
    score, veto, dom = f["score"], f["veto"], f["dom"]
    del score
    lab = (st["dcat"] <= 1.0) & dom
    cols = [C66.robust_rank(f[k], dom) for k in ("amp_snr", "frac", "coh100", "rel_age", "facing", "sharp")]
    cols.append(C66.robust_rank(f["cultural"], dom))
    X = np.stack(cols, -1).reshape(-1, 7)        # flat cell-major design matrix
    names = ["amp_snr", "frac", "coh100", "rel_age", "facing", "sharp", "cultural_index"]
    h, w = dom.shape
    block = 200
    bid = (np.repeat(np.arange((h + block - 1) // block), block)[:h][:, None]
           * ((w + block - 1) // block) + np.repeat(np.arange((w + block - 1) // block), block)[:w][None, :])
    nb = int(bid.max()) + 1
    rng = np.random.default_rng(3)
    picks = rng.choice(nb, size=4, replace=False)
    rows = {}
    sub = {}
    for fold, b in enumerate(picks):
        hold = (bid == b) & dom
        fitm = dom & ~hold
        idx_f = np.nonzero(fitm)[0]
        idx_h = np.nonzero(hold)[0]
        if idx_h.size < 1000 or idx_f.size < 10_000:
            continue
        l1d = lab.ravel()
        pos_f = idx_f[l1d[idx_f]]
        neg_f = idx_f[~l1d[idx_f]]
        if pos_f.size < 500:
            continue
        pos_h, neg_h = idx_h[l1d[idx_h]], idx_h[~l1d[idx_h]]
        if pos_h.size < 200:
            continue
        neg_f = RNG.choice(neg_f, size=min(3 * pos_f.size, neg_f.size), replace=False)
        neg_h = RNG.choice(neg_h, size=min(3 * pos_h.size, neg_h.size), replace=False)
        tr = np.concatenate([pos_f, neg_f])
        te = np.concatenate([pos_h, neg_h])
        ytr, yte = l1d[tr].astype(int), l1d[te].astype(int)
        if ytr.sum() == 0 or yte.sum() == 0:
            continue
        for feats, key in ((slice(0, 6), "channels_only"), (slice(0, 7), "channels_plus_cultural")):
            lr = LogisticRegression(max_iter=400, C=1.0)
            lr.fit(X[tr], ytr)
            pr = lr.decision_function(X[te])
            rows.setdefault(key, []).append(float(roc_auc_score(yte, pr)))
            if key == "channels_plus_cultural":
                sub[fold] = dict(coef_cultural=float(lr.coef_[0][6]),
                                  coef=dict(zip(names, [round(float(c), 4) for c in lr.coef_[0]])))
        if len(rows.get("channels_only", [])) >= 4:
            break
    if len(rows.get("channels_only", [])) < 2:
        raise SystemExit("s3: fewer than 2 usable spatial blocks -- refusing to report a CV AUC")
    out = dict(n_folds_used=len(rows.get("channels_only", [])), generated_utc=now(), label="cell within 100 m of a mapped catalogue fault, lidar-covered footprint",
               cv="4 disjoint 20 km spatial blocks (train off-block, score on-block)",
               auc={k: dict(mean=float(np.mean(v)), ci95=[float(np.mean(v) - 1.96 * np.std(v)), float(np.mean(v) + 1.96 * np.std(v))],
                            folds=[round(x, 4) for x in v]) for k, v in rows.items()},
               delta_auc_channels_plus_cultural_minus_channels_only=round(
                   float(np.mean(rows["channels_plus_cultural"]) - np.mean(rows["channels_only"])), 5),
               fold_coefficients=sub, leakage_note="label is the public catalogue; the lane field itself is catalogue-free, "
                                                   "so this CV measures channel informativeness about mapped faults, not about the hidden panel")
    (EV / "h66_spatial_cv.json").write_text(json.dumps(out, indent=2) + "\n")
    del X
    return out


# ----------------------------------------------------------------------------- s4
def s4_e2_holdout(st) -> dict:
    f = np.load(EV / "h66_fields.npz")
    score, unvet, veto, dom = f["score"], f["score_unvetoed"], f["veto"], f["dom"]
    N = 37_654
    elig = dom & (st["dcat"] > CAT_SEP_PX)
    arms = {"h66_vetoed": _pick(score, elig, N),
            "h66_unvetoed": _pick(unvet, elig, N),
            "h66_random_mass_matched": _random_dots(dom, elig, N, 4242)}
    champ_path = ROOT / "registry/rasters/GEMSDOE32__h33-2-b2-zeros.tif"
    if champ_path.exists():
        with rasterio.open(champ_path) as ds:
            arms["champion_h33_2_b2"] = ds.read(1) > 0
    ctx = H57.build_holdout(st["grid"])
    res = {}
    for name, dots in arms.items():
        r = H57.evaluate(dots, ctx)
        res[name] = {k: r[k] for k in ("emitted_pixels", "on_visible_catalogue", "pooled_dti",
                                       "pooled_coverage", "pooled_tp", "pooled_fp", "pooled_fn",
                                       "pooled_n_truth", "mean_fold_dti", "std_fold_dti", "per_quadrant_dti")}
    # range-front stratification: is the gain confined to range fronts?
    slope = __import__("gems66.spec66", fromlist=["topo_band"]).topo_band(EXT / "topo_10m_derived_100m_u8.tif", "slope_p90")
    rel = __import__("gems66.spec66", fromlist=["topo_band"]).topo_band(EXT / "topo_10m_derived_100m_u8.tif", "relief_local")
    front = dom & (slope >= np.quantile(slope[dom], 0.90)) & (rel >= np.quantile(rel[dom], 0.80))
    strat = {}
    for name, dots in arms.items():
        strat[name] = {}
        for tag, m in (("near_front", front), ("off_front", dom & ~front)):
            r = H57.evaluate(dots & m, ctx)
            strat[name][tag] = dict(pooled_dti=r["pooled_dti"], dots=int((dots & m).sum()),
                                    coverage=r["pooled_coverage"])
    gate = dict(veto_minus_unveto_holdout=round(res["h66_vetoed"]["pooled_dti"] - res["h66_unvetoed"]["pooled_dti"], 6),
                off_front_veto_minus_unveto=round(strat["h66_vetoed"]["off_front"]["pooled_dti"]
                                                  - strat["h66_unvetoed"]["off_front"]["pooled_dti"], 6),
                near_front_veto_minus_unveto=round(strat["h66_vetoed"]["near_front"]["pooled_dti"]
                                                    - strat["h66_unvetoed"]["near_front"]["pooled_dti"], 6))
    out = dict(generated_utc=now(), evidence_class="HOLDOUT-DTI",
               evaluator="gems57-pooled-hide-v2 (4 spatial quadrants x 2 seeds x {all,detached}, whole-segment "
                         "withholding, visible faults masked pixel-exactly, alpha=0.2 beta=0.8, 300 m triangular)",
               withheld_positive_pixels=res["h66_vetoed"]["pooled_n_truth"],
               budget=N, range_front_proxy="lidar-covered cells with 10 m slope_p90 >= p90 and relief_local >= p80",
               results=res, stratified=strat, gate=gate,
               caveat="the registered holdout's truth IS the catalogue, so it is structurally blind to "
                      "off-catalogue placement (IR-INSTR-01, rho=+0.14 vs 12 live owner-reported scores)")
    (EV / "h66_e2_holdout.json").write_text(json.dumps(out, indent=2) + "\n")
    return out


# ----------------------------------------------------------------------------- s5
def s5_emit(st) -> dict:
    """Build the artifact: normalized float32 EPSG:32611 100 m GeoTIFF, NaN only outside."""
    from gems57 import grid as G
    f = np.load(EV / "h66_fields.npz")
    score, veto, dom = f["score"], f["veto"], f["dom"]
    elig = dom & (st["dcat"] > CAT_SEP_PX) & ~veto
    N = 37_654
    dots = _pick(score, elig, N)
    n = int(dots.sum())
    pred = np.zeros(dots.shape, np.float32)
    pred[dots] = 1.0
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    tag = f"gems66-h66-1-scarplet-veto-{n}-{stamp}"
    dl = ROOT / "docs/downloads"
    dl.mkdir(parents=True, exist_ok=True)
    rec = dict(generated_utc=now(), tag=tag, dots=n, budget_requested=N,
               budget_shortfall=int(N - n), eligibility_cells=int(elig.count_nonzero() if hasattr(elig, "count_nonzero") else elig.sum()))
    outs = {}
    for mode in ("allfinite", "nan"):
        name = f"{tag}-{mode}.tif"
        path = dl / name
        if mode == "allfinite":
            G.write_geotiff(path, pred, nodata=None)
        else:
            soft = np.where(st["dom"], pred, np.nan).astype(np.float32)
            import rasterio as rs
            from affine import Affine
            prof = dict(driver="GTiff", height=soft.shape[0], width=soft.shape[1], count=1, dtype="float32",
                        crs="EPSG:32611", transform=Affine(*[float(v) for v in tuple(G.TRANSFORM)[:6]]),
                        tiled=True, blockxsize=256, blockysize=256, compress="deflate", predictor=2, nodata=float("nan"))
            with rs.open(path, "w", **prof) as ds:
                ds.write(soft, 1)
        outs[mode] = str(path.relative_to(ROOT))
    # ZIP (single TIFF inside) for the portal's ".zip containing a single GeoTIFF" option
    import zipfile
    zp = dl / f"{tag}-allfinite.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(dl / f"{tag}-allfinite.tif", arcname=f"{tag}-allfinite.tif")
    outs["zip"] = str(zp.relative_to(ROOT))
    rec["files"] = outs
    # self-consistency: re-read the bytes and recompute the metric terms from them
    with rasterio.open(dl / f"{tag}-allfinite.tif") as ds:
        a = ds.read(1)
    rec["reread"] = dict(dtype=ds.dtypes[0], crs=str(ds.crs), shape=[ds.height, ds.width],
                         vmin=float(a.min()), vmax=float(a.max()), n_positive=int((a > 0).sum()),
                         finite=bool(np.isfinite(a).all()), nodata=str(ds.nodata))
    truth = _offcat_truth(st, dom)
    rec["offcat_instrument"] = instrument(st, a > 0, truth, dom)
    rec["sha256"] = {k: sha256(ROOT / v) for k, v in outs.items()}
    (EV / "h66_emission.json").write_text(json.dumps(rec, indent=2) + "\n")
    return rec


def s4b_detector_holdout(st) -> dict:
    """Gate as the lane paragraph states it: DTI gain on lidar-covered holdout blocks.

    The registered evaluator's truth is *withheld catalogue segments*, so an emission that
    policy-excludes everything within 300 m of the catalogue (s4) cannot score by construction.
    Here the eligibility rule is relaxed to "not on a visible catalogue pixel", which is what
    the evaluator itself masks, so the arm measures detector quality rather than emission policy.
    Both readings are reported; neither is a leaderboard score.
    """
    f = np.load(EV / "h66_fields.npz")
    score, unvet, veto, dom = f["score"], f["score_unvetoed"], f["veto"], f["dom"]
    N = 37_654
    elig = dom & (st["dcat"] > 0.5)
    truth = st["grid"].catalogue
    slope = __import__("gems66.spec66", fromlist=["topo_band"]).topo_band(EXT / "topo_10m_derived_100m_u8.tif", "slope_p90")
    rel = __import__("gems66.spec66", fromlist=["topo_band"]).topo_band(EXT / "topo_10m_derived_100m_u8.tif", "relief_local")
    front = dom & (slope >= np.quantile(slope[dom], 0.90)) & (rel >= np.quantile(rel[dom], 0.80))
    off = dom & ~front
    arms = {"vetoed": _pick(score, elig, N), "unvetoed": _pick(unvet, elig, N),
            "champion_h33_2_b2": None,
            "random_mass_matched": _random_dots(dom, elig, N, 909)}
    cp = ROOT / "registry/rasters/GEMSDOE32__h33-2-b2-zeros.tif"
    if cp.exists():
        with rasterio.open(cp) as ds:
            arms["champion_h33_2_b2"] = ds.read(1) > 0
    ctx = H57.build_holdout(st["grid"])
    out = {"generated_utc": now(), "evidence_class": "HOLDOUT-DTI", "N": N,
           "evaluator": "gems57 pooled hide-and-recover (identical to s4; only the eligibility rule differs)",
           "eligibility": "lidar-covered footprint cells, >=50 m off a visible catalogue pixel",
           "arms": {}}
    for nm, dots in arms.items():
        r = H57.evaluate(dots, ctx)
        ro = H57.evaluate(dots & off, ctx)
        out["arms"][nm] = dict({k: r[k] for k in ("emitted_pixels", "on_visible_catalogue", "pooled_dti",
                                                  "pooled_coverage", "pooled_n_truth", "mean_fold_dti",
                                                  "std_fold_dti", "per_quadrant_dti")},
                               dots_on_front=int((dots & front).sum()), dots_off_front=int((dots & off).sum()),
                               off_front_only={k: ro[k] for k in ("pooled_dti", "pooled_coverage", "emitted_pixels")})
    out.pop("arms", None) if False else None
    out["gate"] = dict(
        channel_beats_random=bool(out["arms"]["unvetoed"]["pooled_dti"] > out["arms"]["random_mass_matched"]["pooled_dti"]),
        veto_helps=bool(out["arms"]["vetoed"]["pooled_dti"] >= out["arms"]["unvetoed"]["pooled_dti"]),
        gain_not_confined_to_range_fronts=bool(
            out["arms"]["unvetoed"]["off_front_only"]["pooled_dti"]
            > out["arms"]["random_mass_matched"]["off_front_only"]["pooled_dti"]))
    (EV / "h66_e2b_detector_holdout.json").write_text(json.dumps(out, indent=2) + "\n")
    return out


STAGES = {"s0": s0_verify, "s1": s1_channels, "s2": s2_e1, "s3": s3_retrain,
          "s4": s4_e2_holdout, "s4b": s4b_detector_holdout, "s5": s5_emit}


def main(argv: list[str]) -> int:
    want = argv[1:] or list(STAGES)
    st = load_state()
    for k in want:
        t0 = time.time()
        out = STAGES[k](st)
        print(f"[{k}] {time.time() - t0:6.1f}s  {json.dumps({kk: vv for kk, vv in list(out.items())[:3]}, default=str)[:300]}")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

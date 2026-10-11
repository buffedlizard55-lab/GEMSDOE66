#!/usr/bin/env python3
"""Historical H66 pipeline plus fail-closed research/release guards.

This file is not the requested native-resolution LIDAR-01 feature implementation. The current
``s1`` decoder consumes a precomputed, quantized 12-band stack and a heuristic cultural/TMI
proxy; its old outputs must not be relabeled as LIDAR-01. The revised ``s4`` requires an
explicitly tagged top-hypothesis field, shared blocked evaluator, and research budget. ``s4b``
is retired. ``s5`` writes only after strict input, holdout, leakage, frozen-best, complete
registry, and official-grid gates pass.

Stages:

  s0  verify every required input byte against an exact pin in ``registry/data_manifest.json``
  s1  decode the historical stack and build its proxy channels (not native Steger/Frangi)
  s2  historical off-catalogue diagnostic (not hidden-fault HOLDOUT-DTI)
  s3  historical spatial-CV diagnostic (not hidden-fault HOLDOUT-DTI)
  s4  shared buffered whole-component spatial holdout; requires a tagged LIDAR-01 proposal
  s4b retired detector-only holdout arm
  s5  release-gated shared-writer GeoTIFF + ZIP; cannot promote old H66 fields

Usage: ``python scripts/run_h66.py s0 s1 s2 ...`` (default: all; ``s0`` always runs first)
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

from gems import holdout as GHOLD                               # noqa: E402
from gems57 import evaluate_holdout as EH57                      # noqa: E402
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


def _array_sha256(value: np.ndarray) -> str:
    """Hash an array's dtype, shape, and C-order bytes for evidence binding."""
    arr = np.ascontiguousarray(value)
    h = hashlib.sha256()
    h.update(arr.dtype.str.encode("ascii"))
    h.update(np.asarray(arr.shape, dtype="<i8").tobytes())
    h.update(arr.tobytes())
    return h.hexdigest()


def _candidate_field_hashes(score, score_unvetoed, dom, veto) -> dict[str, str]:
    """Bind holdout/release evidence to the exact score/mask arrays used for emission."""
    return {
        "score": _array_sha256(np.asarray(score, np.float32)),
        "score_unvetoed": _array_sha256(np.asarray(score_unvetoed, np.float32)),
        "dom": _array_sha256(np.asarray(dom, bool)),
        "veto": _array_sha256(np.asarray(veto, bool)),
    }


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ----------------------------------------------------------------------------- s0
REQUIRED_H66_INPUTS = (
    "training_features.tif",
    "bridge/labels.tif",
    "bridge/existing_faults.tif",
    "bridge/sample_submission.tif",
    "external/lidar_scarp_features_u8.tif",
    "external/lidar_scarp_features.json",
    "external/geodawn_extensions_u8.tif",
    "external/derived_sgmc_faults_100m_u8.tif",
    "external/topo_10m_derived_100m_u8.tif",
)
BUDGETED_STAGES = {"s1", "s2", "s3", "s4", "s4b"}
_INPUTS_VERIFIED = False


def _manifest_rel(raw: str) -> str:
    """Normalize the manifest's repository-relative path to a data-dir relative path."""
    value = str(raw).replace("\\", "/").strip("/")
    return value[5:] if value.startswith("data/") else value


def s0_verify(st=None, *, data_dir: Path | None = None, manifest_path: Path | None = None,
              evidence_dir: Path | None = None) -> dict:
    """Fail closed unless every H66 runtime input exists and has an exact manifest pin.

    A sweep over files that happen to exist cannot prove completeness: missing roles and
    unpinned required rasters are first-class failures. Owner-side receipts are not silently
    promoted into input pins.
    """
    data_dir = Path(data_dir or DATA)
    manifest_path = Path(manifest_path or ROOT / "registry" / "data_manifest.json")
    evidence_dir = Path(evidence_dir or EV)
    pins = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries: dict[str, list[dict]] = {}
    for item in pins.get("files", []):
        for raw in (item.get("path"), item.get("dest")):
            if raw:
                entries.setdefault(_manifest_rel(raw), []).append(item)

    out = {"generated_utc": now(), "required_inputs": list(REQUIRED_H66_INPUTS),
           "checked": {}, "missing": [], "missing_pins": [], "mismatch": [], "pin_conflicts": [],
           "ok": False}
    for rel in REQUIRED_H66_INPUTS:
        path = data_dir / rel
        records = entries.get(rel, [])
        raw_hashes = [rec.get("sha256") for rec in records]
        hashes = sorted({value.lower() for value in raw_hashes
                         if isinstance(value, str) and len(value) == 64
                         and all(char in "0123456789abcdefABCDEF" for char in value)})
        pin_invalid = not records or any(
            not isinstance(value, str) or len(value) != 64
            or any(char not in "0123456789abcdefABCDEF" for char in value)
            for value in raw_hashes)
        if pin_invalid:
            out["missing_pins"].append(rel)
        if len(hashes) > 1:
            out["pin_conflicts"].append(rel)
        if not path.is_file():
            out["missing"].append(rel)
            out["checked"][rel] = {"present": False, "pinned": hashes or None, "match": False}
            continue
        got = sha256(path)
        rec = {"present": True, "sha256": got, "bytes": path.stat().st_size,
               "pinned": hashes[0] if len(hashes) == 1 else hashes or None,
               "match": False}
        if not pin_invalid and len(hashes) == 1:
            rec["match"] = got == hashes[0]
            if got != hashes[0]:
                out["mismatch"].append(rel)
        out["checked"][rel] = rec
    out["ok"] = not any(out[k] for k in ("missing", "missing_pins", "mismatch", "pin_conflicts"))
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / "h66_inputs.json").write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    global _INPUTS_VERIFIED
    _INPUTS_VERIFIED = bool(out["ok"])
    return out


def _research_budget_available(card_path: Path | None = None) -> tuple[bool, str]:
    """Use the canonical card as a hard stop; no experiment starts when either budget is spent."""
    card_path = Path(card_path or ROOT / "docs" / "data" / "run-card.json")
    if not card_path.is_file():
        return False, "canonical run card is missing"
    try:
        budget = json.loads(card_path.read_text(encoding="utf-8"))["budget"]
        used, limit = int(budget["holdout_experiments_used"]), int(budget["max_holdout_experiments"])
        hours, hour_limit = float(budget["wall_time_hours_reported"]), float(budget["max_wall_time_hours"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return False, f"budget record is invalid: {exc}"
    if used >= limit or hours >= hour_limit:
        return False, f"research budget exhausted ({used}/{limit} experiments; {hours:g}/{hour_limit:g} hours)"
    return True, "budget remains"


def _stage_preflight(stage: str) -> None:
    """Prevent direct function calls from bypassing s0 or the canonical research budget."""
    if not _INPUTS_VERIFIED:
        raise RuntimeError(f"{stage} blocked: strict s0 input verification has not passed in this process")
    if stage in BUDGETED_STAGES:
        allowed, reason = _research_budget_available()
        if not allowed:
            raise RuntimeError(f"{stage} blocked before execution: {reason}")


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
    _stage_preflight("s1")
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
    rep = dict(generated_utc=now(), evidence_class="FEATURE-AUC-DIAGNOSTIC; not HOLDOUT-DTI",
               diagnostic_target="public-catalogue proximity inside the lidar-covered footprint; not hidden expert test labels",
               canary_clearance="NOT CLEARED: this diagnostic is not the required feature-alone held-out-fault canary",
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
    _stage_preflight("s2")
    f = np.load(EV / "h66_fields.npz")
    score, unvet, veto, dom = f["score"], f["score_unvetoed"], f["veto"], f["dom"]
    elig = dom & (st["dcat"] > CAT_SEP_PX)
    truth = _offcat_truth(st, dom)
    rep = {"generated_utc": now(), "evidence_class": "OFF-CATALOGUE SGMC PROXY INSTRUMENT; not HOLDOUT-DTI",
           "not_a_competition_score": True,
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
    _stage_preflight("s3")
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
               auc={k: dict(mean=float(np.mean(v)), fold_sd=float(np.std(v)), ci95=None,
                            ci95_status="not computed; folds are not an independent sampling distribution",
                            folds=[round(x, 4) for x in v]) for k, v in rows.items()},
               evidence_class="SPATIAL-CV AUC DIAGNOSTIC; not HOLDOUT-DTI or a competition score",
               delta_auc_channels_plus_cultural_minus_channels_only=round(
                   float(np.mean(rows["channels_plus_cultural"]) - np.mean(rows["channels_only"])), 5),
               fold_coefficients=sub, leakage_note="label is the public catalogue; the lane field itself is catalogue-free, "
                                                   "so this CV measures channel informativeness about mapped faults, not about the hidden panel")
    (EV / "h66_spatial_cv.json").write_text(json.dumps(out, indent=2) + "\n")
    del X
    return out


# ----------------------------------------------------------------------------- s4
HOLDOUT_BLOCK_PX = 200       # 20 km at the 100 m score grid
HOLDOUT_SEEDS = (20, 21)
HOLDOUT_PROTOCOL_ID = "gems66-buffered-whole-component-block-v1"
EXPECTED_TOP_HYPOTHESIS_ID = "LIDAR-01"
FROZEN_BEST_RECORD = ROOT / "registry" / "frozen_holdout_best.json"
REGISTRY_INDEX = ROOT / "evidence" / "registry_full_index.json"


def _feature_planes(fields) -> dict[str, np.ndarray]:
    """Read the candidate's explicit, exhaustive feature manifest for leakage canaries.

    Each feature entering the candidate must be stored as ``feature__<name>`` and named in
    the one-dimensional ``feature_manifest`` array. This avoids silently testing only the
    legacy H66 channels when the proposed native-resolution LIDAR-01 feature set changes.
    """
    keys = set(getattr(fields, "files", fields.keys() if hasattr(fields, "keys") else ()))
    if "feature_manifest" not in keys:
        raise ValueError("candidate lacks the exhaustive feature_manifest required for leakage canaries")
    raw_names = np.asarray(fields["feature_manifest"])
    if raw_names.ndim != 1 or not raw_names.size:
        raise ValueError("feature_manifest must be a non-empty one-dimensional list")
    names = [str(value) for value in raw_names.tolist()]
    if any(not name or name == "None" for name in names) or len(set(names)) != len(names):
        raise ValueError("feature_manifest contains empty or duplicate feature names")
    expected_keys = {f"feature__{name}" for name in names}
    actual_keys = {key for key in keys if key.startswith("feature__")}
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        raise ValueError(f"feature_manifest/feature planes disagree; missing={missing}, extra={extra}")
    result = {}
    for name in names:
        plane = np.asarray(fields[f"feature__{name}"], np.float32)
        if plane.ndim != 2:
            raise ValueError(f"feature {name!r} must be a 2-D raster")
        result[name] = plane
    return result


def _holdout_feature_auc(fields, split: dict, dom: np.ndarray, seed: int) -> dict:
    """AUC for each feature alone against actual held fault pixels in the blocked split.

    Negatives are sampled only from the same held blocks after visible known faults are
    excluded. This is a leakage canary, not a competition score or a model-performance
    estimate. The split's 8-connected components are a disclosed segment proxy when
    authoritative fault-segment IDs are unavailable.
    """
    from sklearn.metrics import roc_auc_score

    region = np.asarray(split["held_block"], bool) & np.asarray(dom, bool)
    truth = np.asarray(split["holdout"], bool) & region
    known = np.asarray(split["visible"], bool)
    # Include the buffer-dropped mapped pixels among known negatives exclusions.
    known_all = np.asarray(split["masked_known"], bool)
    positive = np.flatnonzero(truth)
    negative = np.flatnonzero(region & ~known_all & ~truth)
    if positive.size == 0 or negative.size < 20:
        return {"status": "INCONCLUSIVE", "n_positive": int(positive.size),
                "n_negative_available": int(negative.size), "features": {}}
    n_negative = min(int(negative.size), max(5000, 5 * int(positive.size)))
    rng = np.random.default_rng(60_660_000 + int(seed))
    chosen_negative = rng.choice(negative, size=n_negative, replace=False)
    labels = np.concatenate([np.ones(positive.size, np.uint8), np.zeros(n_negative, np.uint8)])
    features = {}
    for name, plane in _feature_planes(fields).items():
        plane = np.asarray(plane, np.float32)
        if plane.shape != dom.shape:
            raise ValueError(f"feature {name!r} grid shape differs from the holdout")
        values = plane.ravel()
        sampled = np.concatenate([values[positive], values[chosen_negative]])
        if not np.isfinite(sampled).all() or np.ptp(sampled) == 0:
            features[name] = {"auc": None, "auc_reflected": None,
                              "status": "INCONCLUSIVE — constant or non-finite feature"}
            continue
        auc = float(roc_auc_score(labels, sampled))
        reflected = max(auc, 1.0 - auc)
        features[name] = {"auc": auc, "auc_reflected": reflected,
                          "status": "LEAKAGE-SUSPECT" if reflected > 0.90 else "below threshold"}
    tested = [v["auc_reflected"] for v in features.values() if v["auc_reflected"] is not None]
    return {"status": "MEASURED" if tested and all(v["auc_reflected"] is not None for v in features.values())
            else "INCONCLUSIVE", "n_positive": int(positive.size),
            "n_negative_sampled": int(n_negative), "n_negative_available": int(negative.size),
            "features": features, "max_auc_reflected": max(tested) if tested else None}


def _frozen_best() -> tuple[np.ndarray | None, dict]:
    """Load a byte-pinned frozen holdout-best raster; do not infer it from a score claim."""
    if not FROZEN_BEST_RECORD.is_file():
        return None, {"available": False, "reason": "registry/frozen_holdout_best.json is absent"}
    try:
        record = json.loads(FROZEN_BEST_RECORD.read_text(encoding="utf-8"))
        rel = record["file"]
        path = Path(rel)
        if not path.is_absolute():
            path = ROOT / path
        expected = record["sha256"]
        evaluator = record["evaluator_version"]
        if evaluator != EH57.VERSION:
            return None, {"available": False, "reason": "frozen-best evaluator version differs",
                          "recorded_evaluator_version": evaluator}
        if not path.is_file() or sha256(path) != expected:
            return None, {"available": False, "reason": "frozen-best file missing or SHA-256 mismatch"}
        with rasterio.open(path) as ds:
            if (ds.count != 1 or ds.shape != G57.SHAPE or ds.crs is None
                    or ds.crs.to_epsg() != 32611 or ds.transform != G57.TRANSFORM):
                return None, {"available": False, "reason": "frozen-best raster grid is invalid"}
            arr = ds.read(1).astype(np.float32)
        finite = arr[np.isfinite(arr)]
        if not finite.size or (finite < 0.0).any() or (finite > 1.0).any():
            return None, {"available": False, "reason": "frozen-best values are invalid"}
        arr[~np.isfinite(arr)] = 0.0
        return arr, {"available": True, "file": str(path.relative_to(ROOT)),
                     "sha256": expected, "evaluator_version": evaluator,
                     "name": record.get("name", "frozen_holdout_best")}
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return None, {"available": False, "reason": f"invalid frozen-best receipt: {exc}"}


def s4_e2_holdout(st) -> dict:
    """Evaluate a tagged H66 candidate on buffered whole-component spatial blocks.

    Uses the shared ``gems.holdout.spatial_block_holdout`` splitter and the shared
    ``gems57.evaluate_holdout`` pooled metric/bootstrap. It is intentionally protected by
    the project research-budget guard and cannot validate untagged historical fields.
    """
    _stage_preflight("s4")
    fields = np.load(EV / "h66_fields.npz")
    if "hypothesis_id" not in fields:
        raise RuntimeError("s4 refuses historical H66 fields: no top-hypothesis candidate manifest/ID")
    candidate_id = str(np.asarray(fields["hypothesis_id"]).item())
    if candidate_id != EXPECTED_TOP_HYPOTHESIS_ID:
        raise RuntimeError(f"s4 candidate {candidate_id!r} is not the registered top hypothesis {EXPECTED_TOP_HYPOTHESIS_ID}")
    score = np.asarray(fields["score"], np.float32)
    unvetoed = np.asarray(fields["score_unvetoed"], np.float32)
    dom_raw = np.asarray(fields["dom"], bool)
    veto = np.asarray(fields["veto"], bool)
    if any(a.shape != st["grid"].shape for a in (score, unvetoed, dom_raw, veto)):
        raise ValueError("s4 candidate feature/mask shapes differ from the official grid")
    if not np.isfinite(score).all() or not np.isfinite(unvetoed).all():
        raise ValueError("s4 refuses non-finite feature fields")
    candidate_field_hashes = _candidate_field_hashes(score, unvetoed, dom_raw, veto)
    dom = dom_raw & st["grid"].footprint
    frozen, frozen_record = _frozen_best()
    arm_terms: dict[str, np.ndarray] = {}
    split_receipts, canary_splits = [], []
    for seed in HOLDOUT_SEEDS:
        split = GHOLD.spatial_block_holdout(
            st["grid"].catalogue, dom, block_px=HOLDOUT_BLOCK_PX, holdout_fraction=0.20,
            buffer_px=3, seed=seed, min_lidar_fraction=LID_MIN)
        if not split["holdout_fault_cells"] or not split["held_block"].any():
            raise ValueError(f"seed {seed}: no lidar-covered held-out positives")
        # Catalogue-derived eligibility is recomputed from visible faults only. Hidden
        # catalogue pixels are never used to exclude predictions in their own test fold.
        d_visible = ndi.distance_transform_edt(~split["visible"]).astype(np.float32)
        eligible = dom & (d_visible > CAT_SEP_PX)
        if int(eligible.sum()) < 37_654:
            raise ValueError(f"seed {seed}: only {int(eligible.sum())} eligible cells for the fixed 37,654-dot budget")
        candidate = _pick(score, eligible, 37_654)
        controls = {
            "h66_unvetoed": _pick(unvetoed, eligible, 37_654),
            "mass_matched_random": _random_dots(dom, eligible, 37_654, 4242 + seed),
        }
        predictions = {"h66_candidate": candidate, **controls}
        if frozen is not None:
            predictions["frozen_holdout_best"] = frozen
        fold = {
            "region": split["held_block"],
            "truth": split["holdout"],
            "visible": split["visible"],
            "masked_known": st["grid"].catalogue & ~split["held_segment"],
        }
        for arm, prediction in predictions.items():
            result, terms = EH57.evaluate(
                prediction, fold, valid=dom, block_side=HOLDOUT_BLOCK_PX,
                origin=(0, 0), global_shape=dom.shape)
            if arm not in arm_terms:
                arm_terms[arm] = np.zeros_like(terms)
            arm_terms[arm] += terms
        canary_splits.append({"seed": seed,
                              **_holdout_feature_auc(fields, split, dom, seed)})
        split_receipts.append({
            "seed": seed, "splitter": "gems.holdout.spatial_block_holdout",
            "segment_id_source": split["segment_id_source"],
            "held_blocks": split["held_block_ids"],
            "held_segments": split["held_segment_ids"],
            "eligible_blocks": split["eligible_block_count"],
            "withheld_positive_pixels_in_lidar_covered_blocks": split["holdout_fault_cells"],
            "whole_held_segment_pixels": split["held_segment_fault_cells"],
            "buffer_dropped_visible_pixels": split["buffer_dropped_cells"],
            "buffer_px": 3, "block_px": HOLDOUT_BLOCK_PX,
            "visible_pixels_masked_exactly": int((st["grid"].catalogue & ~split["held_segment"]).sum()),
            "catalogue_distance_source": "visible mask only"})

    summary = EH57.pooled_summary(arm_terms, draws=1000, seed=66_2026,
                                  candidate="h66_candidate")
    all_feature_names = sorted(set().union(*(set(x.get("features", {})) for x in canary_splits)))
    max_by_feature = {}
    for name in all_feature_names:
        vals = [row.get("features", {}).get(name, {}).get("auc_reflected") for row in canary_splits]
        max_by_feature[name] = max(vals) if vals and all(v is not None for v in vals) else None
    canary_complete = bool(max_by_feature) and all(v is not None for v in max_by_feature.values())
    canary_max = max((v for v in max_by_feature.values() if v is not None), default=None)
    canary_status = ("PASS" if canary_complete and canary_max <= 0.90 else
                     "LEAKAGE-SUSPECT" if canary_max is not None and canary_max > 0.90 else
                     "INCONCLUSIVE")
    score_rows = summary["scores"]
    diffs = summary["paired_differences"]
    frozen_diff = diffs.get("frozen_holdout_best")
    frozen_win = bool(frozen_record.get("available") and frozen_diff and
                      frozen_diff.get("ci95") and frozen_diff["ci95"][0] > 0.0)
    out = {
        "generated_utc": now(), "evidence_class": "HOLDOUT-DTI",
        "protocol_id": HOLDOUT_PROTOCOL_ID,
        "evaluator_version": EH57.VERSION,
        "splitter": "gems.holdout.spatial_block_holdout (8-connected whole-component proxy; 20 km blocks; 3 px buffer)",
        "metric": {"alpha": summary["alpha"], "beta": summary["beta"],
                   "triangular_radius_m": summary["triangular_radius_m"]},
        "hypothesis_id": candidate_id,
        "candidate_arm": "h66_candidate",
        "candidate_field_hashes": candidate_field_hashes,
        "candidate": score_rows["h66_candidate"],
        "withheld_positive_count": score_rows["h66_candidate"]["withheld_positive_pixels"],
        "scores": score_rows,
        "paired_differences": diffs,
        "bootstrap": summary["bootstrap"],
        "frozen_holdout_best": {**frozen_record, "candidate_beats_best_with_paired_ci": frozen_win,
                                 "paired_difference": frozen_diff},
        "feature_alone_leakage_canary": {
            "rule": "AUC >0.90 on held-out faults is leakage until disproven",
            "status": canary_status, "max_auc_reflected": canary_max,
            "per_feature_max_auc_reflected": max_by_feature,
            "per_split": canary_splits,
            "not_a_dti_score": True},
        "split_receipts": split_receipts,
        "range_front_stratification": {
            "status": "NOT RUN — no validated range-front polygon was available; do not use the historical slope/relief proxy as a geographic truth.",
            "values": None},
        "gates": {
            "candidate_beats_frozen_holdout_best": frozen_win,
            "feature_alone_canary_pass": canary_status == "PASS",
            "ci95_present": bool(score_rows["h66_candidate"].get("ci95")),
        },
        "source_hashes": {
            "runner_sha256": sha256(Path(__file__).resolve()),
            "shared_holdout_sha256": sha256(ROOT / "src" / "gems" / "holdout.py"),
            "shared_evaluator_sha256": sha256(ROOT / "src" / "gems57" / "evaluate_holdout.py"),
        },
        "not_a_leaderboard_score": True,
    }
    (EV / "h66_e2_holdout.json").write_text(json.dumps(out, indent=2, allow_nan=False) + "\n")
    return out


def s4b_detector_holdout(st) -> dict:
    _stage_preflight("s4b")
    raise RuntimeError("s4b is retired: the detector arm is not the emitted policy. Use the single s4 whole-segment blocked holdout after a separately authorized budget reset.")


def _release_evidence_failures() -> list[str]:
    """Return every missing/failed evidence gate. This check must run before any TIFF write."""
    failures = []
    try:
        inputs = json.loads((EV / "h66_inputs.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        inputs = {}
    if not isinstance(inputs, dict):
        inputs = {}
    if inputs.get("ok") is not True:
        failures.append("required H66 input bytes/pins are missing or mismatched")
    try:
        holdout = json.loads((EV / "h66_e2_holdout.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        holdout = {}
    if not isinstance(holdout, dict):
        holdout = {}

    if holdout.get("protocol_id") != HOLDOUT_PROTOCOL_ID:
        failures.append("required buffered whole-component spatial holdout is missing")
    if holdout.get("hypothesis_id") != EXPECTED_TOP_HYPOTHESIS_ID or holdout.get("candidate_arm") != "h66_candidate":
        failures.append("holdout is not for the registered top-hypothesis candidate arm")
    if holdout.get("evidence_class") != "HOLDOUT-DTI" or holdout.get("evaluator_version") != EH57.VERSION:
        failures.append("required shared HOLDOUT-DTI evaluator result/version is missing")

    metric = holdout.get("metric", {})
    if not isinstance(metric, dict):
        metric = {}
    if (metric.get("alpha") != M57.ALPHA or metric.get("beta") != M57.BETA
            or metric.get("triangular_radius_m") != M57.R_M):
        failures.append("holdout metric parameters do not match the shared competition DTI")
    receipts = holdout.get("split_receipts")
    if (not isinstance(receipts, list)
            or {r.get("seed") for r in receipts if isinstance(r, dict)} != set(HOLDOUT_SEEDS)
            or any(not isinstance(r, dict) or r.get("buffer_px") != 3
                   or r.get("block_px") != HOLDOUT_BLOCK_PX
                   or r.get("catalogue_distance_source") != "visible mask only"
                   or not isinstance(r.get("withheld_positive_pixels_in_lidar_covered_blocks"), int)
                   or r.get("withheld_positive_pixels_in_lidar_covered_blocks", 0) <= 0
                   for r in receipts)):
        failures.append("holdout split receipts do not prove both buffered lidar-covered spatial folds")

    candidate = holdout.get("candidate", {})
    if not isinstance(candidate, dict):
        candidate = {}
    ci = candidate.get("ci95")
    is_number = lambda x: isinstance(x, (int, float)) and not isinstance(x, bool) and np.isfinite(x)
    count = candidate.get("withheld_positive_pixels")
    dti = candidate.get("dti")
    ci_ok = (isinstance(ci, list) and len(ci) == 2 and all(is_number(x) and 0.0 <= x <= 1.0 for x in ci)
             and ci[0] <= ci[1])
    if (candidate.get("evidence_class") != "HOLDOUT-DTI"
            or candidate.get("evaluator_version") != EH57.VERSION
            or not isinstance(count, int) or isinstance(count, bool) or count <= 0
            or holdout.get("withheld_positive_count") != count
            or not is_number(dti) or not 0.0 <= dti <= 1.0
            or not ci_ok):
        failures.append("candidate HOLDOUT-DTI value, evaluator, positive count, or 95% CI is missing/invalid")

    hashes = holdout.get("candidate_field_hashes", {})
    required_hashes = {"score", "score_unvetoed", "dom", "veto"}
    hashes_ok = (isinstance(hashes, dict) and set(hashes) == required_hashes
                 and all(isinstance(v, str) and len(v) == 64
                         and all(c in "0123456789abcdef" for c in v.lower()) for v in hashes.values()))
    if not hashes_ok:
        failures.append("holdout is not bound to the exact candidate score/domain/veto field hashes")

    source_hashes = holdout.get("source_hashes", {})
    if not isinstance(source_hashes, dict):
        source_hashes = {}
    current_hashes = {
        "runner_sha256": sha256(Path(__file__).resolve()),
        "shared_holdout_sha256": sha256(ROOT / "src" / "gems" / "holdout.py"),
        "shared_evaluator_sha256": sha256(ROOT / "src" / "gems57" / "evaluate_holdout.py"),
    }
    if any(source_hashes.get(key) != value for key, value in current_hashes.items()):
        failures.append("holdout source hashes do not match the current runner/shared evaluator")

    frozen = holdout.get("frozen_holdout_best", {})
    if not isinstance(frozen, dict):
        frozen = {}
    diff = frozen.get("paired_difference") or {}
    if not isinstance(diff, dict):
        diff = {}
    diff_ci = diff.get("ci95")
    diff_ci_ok = (isinstance(diff_ci, list) and len(diff_ci) == 2
                  and all(is_number(x) and -1.0 <= x <= 1.0 for x in diff_ci)
                  and diff_ci[0] <= diff_ci[1])
    current_best, current_best_record = _frozen_best()
    if not isinstance(current_best_record, dict):
        current_best_record = {}
    frozen_matches_current = (
        current_best is not None and current_best_record.get("available") is True
        and frozen.get("sha256") == current_best_record.get("sha256")
        and frozen.get("evaluator_version") == EH57.VERSION
        and frozen.get("file") == current_best_record.get("file"))
    if (frozen.get("available") is not True or not frozen_matches_current
            or frozen.get("candidate_beats_best_with_paired_ci") is not True
            or diff.get("evidence_class") != "HOLDOUT-DTI" or not diff_ci_ok or diff_ci[0] <= 0.0
            or diff.get("withheld_positive_pixels") != count):
        failures.append("candidate has not beaten the current hash-pinned frozen holdout best with paired 95% CI")

    canary = holdout.get("feature_alone_leakage_canary", {})
    if not isinstance(canary, dict):
        canary = {}
    per_feature = canary.get("per_feature_max_auc_reflected", {})
    if not isinstance(per_feature, dict):
        per_feature = {}
    canary_max = canary.get("max_auc_reflected")
    if (canary.get("status") != "PASS" or not isinstance(per_feature, dict) or not per_feature
            or not is_number(canary_max) or not 0.0 <= canary_max <= 0.90
            or any(not is_number(value) or not 0.0 <= value <= 0.90 for value in per_feature.values())):
        failures.append("feature-alone held-fault leakage canary did not pass or is incomplete")
    return failures


def _registry_uniqueness_gate(surface: np.ndarray, dots: np.ndarray, grid, footprint: np.ndarray) -> tuple[bool, dict]:
    """Run both literal registry checks; missing/incomplete indices are never a pass."""
    from gems57 import uniqueness as U57
    index_path = REGISTRY_INDEX
    if not index_path.is_file():
        return False, {"status": "INCONCLUSIVE", "reason": f"complete registry index absent: {index_path.relative_to(ROOT)}"}
    expected_grid = (grid.shape, grid.crs, grid.transform)
    reports = {}
    for stage, candidate, phase in (("pre_placement_surface", surface, "surface"),
                                    ("post_placement_dots", dots, "emitted")):
        report = U57.compare_array_to_registry(
            candidate, index_path, footprint, expected_grid=expected_grid, phase=phase)
        reports[stage] = report
        (EV / f"h66_uniqueness_{stage}.json").write_text(
            json.dumps(report, indent=2, allow_nan=False) + "\n")
    passed = all(r.get("complete_accessible_scan") is True and r.get("unique") is True
                 and r.get("missing_or_invalid", 1) == 0 and not r.get("source_errors")
                 for r in reports.values())
    return passed, reports


def s5_emit(st) -> dict:
    """Write a unique competition TIFF only after all scientific/release gates pass."""
    _stage_preflight("s5")
    current_inputs = s0_verify()
    if not current_inputs.get("ok"):
        raise RuntimeError("release blocked: strict s0 no longer verifies current inputs; no TIFF written")
    failures = _release_evidence_failures()
    if failures:
        rep = {"generated_utc": now(), "release_cleared": False,
               "tiff_written": False, "failures": failures}
        (EV / "h66_release_preflight.json").write_text(json.dumps(rep, indent=2) + "\n")
        raise RuntimeError("release blocked; no TIFF written: " + "; ".join(failures))

    from gems.submission_writer import write_submission
    from gems.validate_submission import validate
    import os
    import shutil
    import tempfile
    import zipfile

    fields = np.load(EV / "h66_fields.npz")
    if "hypothesis_id" not in fields or str(np.asarray(fields["hypothesis_id"]).item()) != EXPECTED_TOP_HYPOTHESIS_ID:
        raise RuntimeError("s5 refuses untagged historical fields; no LIDAR-01 candidate raster exists")
    score = np.asarray(fields["score"], np.float32)
    score_unvetoed = np.asarray(fields["score_unvetoed"], np.float32)
    veto = np.asarray(fields["veto"], bool)
    dom = np.asarray(fields["dom"], bool)
    holdout = json.loads((EV / "h66_e2_holdout.json").read_text(encoding="utf-8"))
    if _candidate_field_hashes(score, score_unvetoed, dom, veto) != holdout.get("candidate_field_hashes"):
        raise RuntimeError("s5 candidate score/domain/veto fields differ from the validated HOLDOUT-DTI fields")
    elig = dom & (st["dcat"] > CAT_SEP_PX) & ~veto
    dots = _pick(score, elig, 37_654)
    pred = np.zeros(dots.shape, np.float32)
    pred[dots] = 1.0
    registry_ok, registry_reports = _registry_uniqueness_gate(score, pred, st["grid"], st["grid"].footprint)
    if not registry_ok:
        rep = {"generated_utc": now(), "release_cleared": False,
               "tiff_written": False, "registry": registry_reports,
               "failures": ["pre-placement surface and/or final-dot registry check failed or was incomplete"]}
        (EV / "h66_release_preflight.json").write_text(json.dumps(rep, indent=2, allow_nan=False) + "\n")
        raise RuntimeError("release blocked by incomplete or failed uniqueness registry; no TIFF written")

    note = "Native-resolution lidar scarp channels; spatially blocked validation; see run card."
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    name = f"GEMSDOE66-LIDAR-SCARP-{int(dots.sum())}-{stamp}"
    final_path = ROOT / "docs" / "downloads" / f"{name}.tif"
    sample = DATA / "bridge" / "sample_submission.tif"
    features = DATA / "training_features.tif"
    with tempfile.TemporaryDirectory(prefix="h66-release-", dir=EV) as tmpdir:
        temp_path = Path(tmpdir) / "candidate.tif"
        receipt = write_submission(temp_path, pred, st["grid"].footprint, sample,
                                  name=name, note=note)
        validator = validate(temp_path, reference_path=sample, features_path=features)
        if validator.get("passed") is not True or validator.get("skipped_checks_mean_unverified"):
            rep = {"generated_utc": now(), "release_cleared": False, "tiff_written": False,
                   "writer_receipt": receipt, "validator": validator,
                   "failures": ["shared official-grid validator did not fully pass"]}
            (EV / "h66_release_preflight.json").write_text(json.dumps(rep, indent=2) + "\n")
            raise RuntimeError("shared official-grid validator failed; no downloadable TIFF written")
        with rasterio.open(temp_path) as ds:
            on_disk = ds.read(1).astype(np.float32)
            disk_grid_ok = (ds.count == 1 and ds.shape == st["grid"].shape
                            and ds.crs == st["grid"].crs and ds.transform == st["grid"].transform)
        fp = st["grid"].footprint
        if (not disk_grid_ok or not np.array_equal(on_disk[fp], pred[fp])
                or not np.isnan(on_disk[~fp]).all() or sha256(temp_path) != receipt["sha256"]):
            rep = {"generated_utc": now(), "release_cleared": False, "tiff_written": False,
                   "writer_receipt": receipt, "validator": validator,
                   "failures": ["writer output bytes/pixels/grid differ from the checked candidate"]}
            (EV / "h66_release_preflight.json").write_text(json.dumps(rep, indent=2) + "\n")
            raise RuntimeError("shared writer output failed exact on-disk verification; no TIFF placed")
        # Compare the decoded on-disk candidate, normalized outside the official footprint,
        # against the complete registry; the raw output hash is checked in the same pass.
        from gems57 import uniqueness as U57
        emitted = np.where(fp, on_disk, 0.0).astype(np.float32)
        final_uniqueness = U57.compare_array_to_registry(
            emitted, REGISTRY_INDEX, fp, file_sha256=receipt["sha256"],
            expected_grid=(st["grid"].shape, st["grid"].crs, st["grid"].transform),
            phase="emitted")
        if final_uniqueness.get("complete_accessible_scan") is not True or final_uniqueness.get("unique") is not True:
            (EV / "h66_uniqueness_final_bytes.json").write_text(
                json.dumps(final_uniqueness, indent=2, allow_nan=False) + "\n")
            raise RuntimeError("on-disk TIFF hash/pixel registry check failed; no downloadable TIFF written")
        final_path.parent.mkdir(parents=True, exist_ok=True)
        zip_path = final_path.with_suffix(".zip")
        if final_path.exists() or zip_path.exists():
            raise FileExistsError("refusing to overwrite an existing candidate download")
        staged_zip = Path(tmpdir) / f"{name}.zip"
        with zipfile.ZipFile(staged_zip, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.write(temp_path, arcname=final_path.name)
        with zipfile.ZipFile(staged_zip, "r") as archive:
            if archive.testzip() is not None or archive.namelist() != [final_path.name]:
                raise RuntimeError("staged submission ZIP failed integrity checks")
        final_receipt = dict(receipt, file=final_path.name,
                             receipt_kind="local shared-writer receipt; NOT an organizer receipt")
        try:
            os.replace(temp_path, final_path)
            if sha256(final_path) != receipt["sha256"]:
                raise RuntimeError("placed TIFF hash differs from shared-writer receipt")
            os.replace(staged_zip, zip_path)
            Path(str(final_path) + ".receipt.json").write_text(
                json.dumps(final_receipt, indent=2) + "\n")
        except Exception:
            final_path.unlink(missing_ok=True)
            zip_path.unlink(missing_ok=True)
            Path(str(final_path) + ".receipt.json").unlink(missing_ok=True)
            raise
    result = {"generated_utc": now(), "tiff_written": True, "file": str(final_path.relative_to(ROOT)),
              "zip": str(zip_path.relative_to(ROOT)), "sha256": receipt["sha256"],
              "name": name, "note": note, "note_chars": len(note), "writer_receipt": final_receipt,
              "validator": validator, "registry": registry_reports,
              "release_cleared": True}
    (EV / "h66_emission.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


STAGES = {"s0": s0_verify, "s1": s1_channels, "s2": s2_e1, "s3": s3_retrain,
          "s4": s4_e2_holdout, "s4b": s4b_detector_holdout, "s5": s5_emit}


def main(argv: list[str]) -> int:
    want = argv[1:] or list(STAGES)
    unknown = [k for k in want if k not in STAGES]
    if unknown:
        raise SystemExit(f"unknown stages: {unknown}; valid stages: {sorted(STAGES)}")
    # s0 is always first and never loads project arrays. Missing inputs/pins are a
    # documented exit, not an exception hidden behind load_state().
    t0 = time.time()
    inputs = s0_verify()
    print(f"[s0] {time.time() - t0:6.1f}s  ok={inputs['ok']} missing={inputs['missing']} "
          f"missing_pins={inputs['missing_pins']} mismatch={inputs['mismatch']}")
    sys.stdout.flush()
    if not inputs["ok"]:
        return 2
    if any(k in BUDGETED_STAGES for k in want):
        allowed, reason = _research_budget_available()
        if not allowed:
            raise SystemExit(f"research stopped before any experiment: {reason}")
    st = load_state()
    for k in want:
        if k == "s0":
            continue
        t0 = time.time()
        out = STAGES[k](st)
        print(f"[{k}] {time.time() - t0:6.1f}s  {json.dumps({kk: vv for kk, vv in list(out.items())[:3]}, default=str)[:300]}")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

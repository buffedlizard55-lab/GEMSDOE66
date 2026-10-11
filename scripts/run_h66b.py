#!/usr/bin/env python3
"""H66-2 runner: strike-coherent antislope scarp chains on the native-resolution LiDAR stack.

Lane paragraph (from the project charter, this repository's standing protocol):
  "Native-resolution lidar scarp channels ... (i) scarplet template matching ...
   extended with slope-aware scarp templates ... (ii) Steger sub-pixel ridge/valley lines
   and Frangi multiscale Hessian line measures at 2-20 m scales on a slope-detrended
   surface.  Aggregate to 100 m cells as scarp-pixel fraction, SNR-weighted amplitude,
   structure-tensor orientation coherence and dominant strike.  Mask roads, canals and
   field edges with the existing cultural-feature mask, then retrain under spatial CV.
   Gate: DTI gain on lidar-covered holdout blocks that is not confined to range fronts."

Difference from H66-1 (what is new here)
----------------------------------------
H66-1 built ONE blend -- 0.35*rank(amp_snr) + 0.25*rank(frac) + 0.25*rank(coh) +
0.15*rank(rel_age) -- emitted it as NMS dots and spent its experiment budget on a
cultural-feature veto that measured as a clean negative.  H66-2 keeps the same pinned
inputs and the same emission machinery but asks two untouched questions inside the lane:

  E1  channel ablation on a population-matched instrument: do the four named aggregates
      actually carry the off-catalogue signal, and does the *dip-sense* channel
      (``facing`` = (downface-upface)/(downface+upface), computed by H66-1 but never
      used) or a concordance product add anything?  Every arm is reported.
  E2  emission geometry: the official metric's TP term is a max over a 300 m kernel, so
      a chain of pixels along one trace buys one kernel credit per truth pixel while a
      sparse dot buys the same credit from one pixel.  Does a strike-coherent chain
      (built only from the pinned ``strike`` band) beat NMS dots at equal mass?
  E3  mass sweep on the winning field, then the format-validated artifact + validator +
      uniqueness + run card.

Stages:  e1  e2  e3      (default: all)
Evidence: evidence/h66b_*.json   -- each stage writes before the next starts.
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
from gems57 import metric as M                                   # noqa: E402
from gems66 import channels66 as C66                             # noqa: E402

DATA = ROOT / "data"
EXT = DATA / "external"
EV = ROOT / "evidence"
EV.mkdir(exist_ok=True)
LID_MIN = 0.5
CAT_SEP_PX = 3.0
NMS_PX = 2.8                     # family thinning convention (r7-nms3, H66-1)
N_RANDOM = 5
RNG_SEED = 66201

BANDS = ("ex_max", "ex_mean", "step_max", "lapneg_max", "lappos_max", "downface_max",
         "upface_max", "cross_max", "relief", "coh100", "strike", "valid")


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


# --------------------------------------------------------------------------- shared
def load_state() -> dict:
    lab = _read("data/bridge/labels.tif").astype(np.float64)
    foot = lab != -1
    cat = lab == 1
    sgmc = _read("data/external/sgmc_faults_100m.tif") > 0
    dcat = ndi.distance_transform_edt(~cat).astype(np.float32)
    dom = foot & (dcat > CAT_SEP_PX)          # emission eligibility, champion's own min
    return dict(foot=foot, cat=cat, sgmc=sgmc & foot, dcat=dcat, dom=dom)


def _read(rel: str) -> np.ndarray:
    with rasterio.open(ROOT / rel) as ds:
        return ds.read(1)


def channels(state) -> C66.Channels:
    ch = C66.build_channels(EXT, state["foot"])
    state["ch"] = ch
    return ch


def nms_pick(score: np.ndarray, elig: np.ndarray, n: int) -> np.ndarray:
    """Top-n of ``score`` inside ``elig`` with the family's 2.8 px maximum-filter NMS."""
    s = np.where(elig, score, 0.0).astype(np.float32)
    yy, xx = np.mgrid[-3:4, -3:4]
    foot = np.zeros((7, 7), bool)
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


def instrument(field: np.ndarray, state) -> dict:
    """Official-metric terms against the population-matched off-catalogue SGMC band."""
    truth = state["sgmc"] & (state["dcat"] > CAT_SEP_PX)
    r = M.dti_exact(field, truth, valid=state["foot"], known=state["cat"])
    mass = float(np.where(state["dom"], np.maximum(field, 0.0), 0.0).sum())
    return dict(n_dots=int((field > 0).sum()), mass=mass, t=r["tp"], f=r["fp"], fn=r["fn"],
                n_truth=r["n_truth"], dti=r["dti"], coverage=r["coverage"],
                credit_per_dot=(r["tp"] / mass) if mass > 0 else 0.0)


def random_control(state, n: int, draws: int = N_RANDOM) -> dict:
    rng = np.random.default_rng(RNG_SEED)
    ys, xs = np.nonzero(state["dom"])
    out = []
    for _ in range(draws):
        pick = rng.choice(len(ys), size=min(n, len(ys)), replace=False)
        f = np.zeros(state["foot"].shape, np.float32)
        f[ys[pick], xs[pick]] = 1.0
        out.append(instrument(f, state))
    return dict(n=draws, dti_mean=float(np.mean([o["dti"] for o in out])),
                dti_sd=float(np.std([o["dti"] for o in out])),
                credit_per_dot_mean=float(np.mean([o["credit_per_dot"] for o in out])),
                credit_per_dot_sd=float(np.std([o["credit_per_dot"] for o in out])))


# --------------------------------------------------------------------------- fields
def field_arms(ch: C66.Channels, state) -> dict[str, np.ndarray]:
    """Every candidate scalar field, built only from the pinned LiDAR/topo stack.

    Ranks are computed inside the LiDAR-covered domain, exactly as H66-1 does.  The
    ``facing`` channel sign is the one physical question E1 asks: a basin-facing normal
    scarp steps *down* against the 30-100 m regional upslope, so ``+facing`` should beat
    ``-facing``; both signs are measured rather than assumed.
    """
    dom = ch.covered
    z = np.nan_to_num
    r = {k: C66.robust_rank(z(v), dom) for k, v in
         dict(amp_snr=ch.amp_snr, frac=ch.frac, coh=ch.coh_cell, age=ch.rel_age,
              face=ch.facing, sharp=ch.sharp, height=ch.height_m, step=ch.step,
              relief=ch.relief_m, amp=ch.amp, snr=ch.snr).items()}
    r["antiface"] = 1.0 - r["face"]
    R, ang, _ = C66.circ_windowed_strike(z(ch.strike), z(ch.amp_snr), 15)
    r["strikecoh"] = C66.robust_rank(np.where(np.isfinite(R), R, 0.0), dom)
    arms = {
        # the four named aggregates, alone (leakage/ablation canary)
        "amp_snr_only": r["amp_snr"], "frac_only": r["frac"], "coh_only": r["coh"],
        "age_only": r["age"],
        # the aggregates H66-1 computed and never used
        "face_only": r["face"], "antiface_only": r["antiface"], "sharp_only": r["sharp"],
        "height_only": r["height"], "relief_only": r["relief"], "strikecoh_only": r["strikecoh"],
        # H66-1 baseline
        "h66_1_blend": 0.35 * r["amp_snr"] + 0.25 * r["frac"] + 0.25 * r["coh"] + 0.15 * r["age"],
        # dip-sense added (basin-facing scarps preferred, both signs)
        "blend_plus_face": (0.30 * r["amp_snr"] + 0.20 * r["frac"] + 0.20 * r["coh"]
                            + 0.15 * r["age"] + 0.15 * r["face"]),
        "blend_plus_antiface": (0.30 * r["amp_snr"] + 0.20 * r["frac"] + 0.20 * r["coh"]
                                + 0.15 * r["age"] + 0.15 * r["antiface"]),
        # concordance: a real scarp must fire several independent channels at once
        "concordance_geo": (r["amp_snr"] * r["frac"] * r["coh"] * r["sharp"]) ** 0.25,
        "concordance_step_face": (r["step"] * r["antiface"] * r["sharp"]) ** (1.0 / 3.0),
        # antislope-amplitude: amplitude weighted by dip-sense and coherence
        "amp_x_antiface_coh": r["amp_snr"] * r["antiface"] * (0.5 + 0.5 * r["coh"]),
    }
    return {k: np.where(dom, v, 0.0).astype(np.float32) for k, v in arms.items()}


# --------------------------------------------------------------------------- e1
def e1_ablation(state) -> dict:
    ch = channels(state)
    arms = field_arms(ch, state)
    N = 37_654                                  # mass-matched to the live-scored champion
    rep = dict(generated_utc=now(), evidence_class="OFF-CATALOGUE-PROXY (field quality, not a score)",
               instrument="pooled DTI (alpha .2 beta .8, 300 m triangular) vs USGS SGMC faults >300 m "
                          "from the published catalogue, footprint-restricted, catalogue excluded",
               truth_pixels=int((state["sgmc"] & (state["dcat"] > CAT_SEP_PX)).sum()),
               eligibility_cells=int(state["dom"].sum()), budget=N, nms_px=NMS_PX, arms={})
    rand = random_control(state, N)
    rep["random_mass_matched"] = rand
    for name, f in arms.items():
        dots = nms_pick(f, state["dom"], N)
        rec = instrument(dots.astype(np.float64), state)
        rec["excess_over_random"] = rec["credit_per_dot"] - rand["credit_per_dot_mean"]
        rec["ratio_over_random"] = rec["credit_per_dot"] / max(rand["credit_per_dot_mean"], 1e-9)
        rep["arms"][name] = rec
        print(f"  E1 {name:22s} n={rec['n_dots']:6d} dti={rec['dti']:.5f} "
              f"cpd={rec['credit_per_dot']:.4f} x{rec['ratio_over_random']:.2f}", flush=True)
    np.savez_compressed(EV / "h66b_fields.npz", **{k: v.astype(np.float32) for k, v in arms.items()},
                        dom=state["dom"])
    (EV / "h66b_e1_ablation.json").write_text(json.dumps(rep, indent=2) + "\n")
    return rep


# --------------------------------------------------------------------------- e2
def chain_emit(field: np.ndarray, state, n: int, min_chain: int = 3,
               strike_band: np.ndarray | None = None, ang_tol_deg: float = 30.0) -> np.ndarray:
    """Strike-coherent chain emission at a fixed mass budget.

    1. seed = NMS peaks of ``field`` inside the eligible domain (same machinery as dots);
    2. grow each seed along its own strike band direction into a chain, accepting a
       neighbour cell only if (a) it is inside the eligible domain, (b) its field value
       is in the top ``grow_pct`` of the domain, and (c) its own ``strike`` band differs
       from the chain's first-seed strike by <= ``ang_tol_deg`` (the strike band is a
       modulo-180 orientation, so the comparison is done on doubled angles);
    3. stop when the budget is spent, taking seeds in descending field value (so a
       chain that cannot be started falls back to its seed dot rather than being lost).
    """
    dom = state["dom"]
    seeds = nms_pick(field, dom, n)
    ys, xs = np.nonzero(seeds)
    order = np.argsort(-field[ys, xs])
    ys, xs = ys[order], xs[order]
    out = np.zeros(field.shape, bool)
    if strike_band is None:
        strike_band = _read("data/external/lidar_scarp_features_u8.tif")  # unused fallback
    thr = float(np.quantile(field[dom], 1.0 - 0.25))     # only top-25% cells may extend a chain
    h, w = field.shape
    left = n
    for y0, x0 in zip(ys, xs):
        if left <= 0:
            break
        out[y0, x0] = True
        left -= 1
        if left <= 0:
            break
        th0 = float(strike_band[y0, x0]) * 2.0
        for sgn in (1, -1):
            y, x = y0, x0
            d = np.deg2rad(th0)
            dy, dx = -np.cos(d), np.sin(d)          # strike direction on (row, col)
            step = 1
            while left > 0 and step <= 40:
                y = int(round(y0 + sgn * dy * step))
                x = int(round(x0 + sgn * dx * step))
                if not (0 <= y < h and 0 <= x < w):
                    break
                # orientation agreement with the seed's strike (mod 180 deg)
                if np.isfinite(strike_band[y, x]):
                    dth = abs(float(strike_band[y, x]) * 2.0 - th0) % 360.0
                    dth = min(dth, 360.0 - dth) / 2.0
                    if dth > ang_tol_deg:
                        break
                if not dom[y, x]:
                    break
                if field[y, x] < thr and step > 1:
                    break
                if not out[y, x]:
                    out[y, x] = True
                    left -= 1
                step += 1
    return out


def e2_geometry(state) -> dict:
    from gems66.spec66 import read_bands
    f = np.load(EV / "h66b_fields.npz")
    dom = f["dom"]
    strike = read_bands(EXT / "lidar_scarp_features_u8.tif", ("strike",))["strike"]
    strike = np.where(dom, strike, np.nan)
    win = ("h66_1_blend", "blend_plus_antiface", "concordance_step_face")
    rep = dict(generated_utc=now(), evidence_class="OFF-CATALOGUE-PROXY (emission geometry)",
               instrument="same as E1", eligibility_cells=int(dom.sum()),
               chain_rule="seed=NMS(field,2.8px); grow along the pinned strike band while the "
                          "neighbour stays in-domain, in the top-25% of the field, and within "
                          "30 deg (mod 180) of the seed strike; budget shared by descending seed value",
               arms={})
    for name in win:
        field = f[name]
        rep["arms"][name] = {}
        for n in (20_000, 37_654):
            d = nms_pick(field, dom, n)
            c = chain_emit(field, state, n, strike_band=strike)
            for tag, m in (("dots", d), ("chains", c)):
                rec = instrument(m.astype(np.float64), state)
                rec["n_emitted"] = int(m.sum())
                rep["arms"][name][f"{tag}_{n}"] = rec
                print(f"  E2 {name:22s} {tag:7s} n={n:6d} emitted={rec['n_emitted']:6d} "
                      f"cpd={rec['credit_per_dot']:.4f} dti={rec['dti']:.5f}", flush=True)
    (EV / "h66b_e2_geometry.json").write_text(json.dumps(rep, indent=2) + "\n")
    return rep


# --------------------------------------------------------------------------- e3
def e3_mass_and_gate(state) -> dict:
    """Mass sweep on the winning field + the registered holdout + the lane's stratification."""
    from gems57 import holdout as H57
    from gems57 import grid as G57
    from gems66.spec66 import topo_band
    f = np.load(EV / "h66b_fields.npz")
    e1 = json.loads((EV / "h66b_e1_ablation.json").read_text())
    best = max(e1["arms"], key=lambda k: e1["arms"][k]["credit_per_dot"])
    field = f[best]
    dom = f["dom"]
    rep = dict(generated_utc=now(), evidence_class="OFF-CATALOGUE-PROXY + HOLDOUT-DTI",
               chosen_field=best, budget_sweep={})
    truth = state["sgmc"] & (state["dcat"] > CAT_SEP_PX)
    for n in (6_000, 12_000, 20_000, 37_654, 60_000, 90_000):
        dots = nms_pick(field, dom, n)
        rec = instrument(dots.astype(np.float64), state)
        rec["n_emitted"] = int(dots.sum())
        rep["budget_sweep"][n] = rec
        print(f"  E3 N={n:6d} emitted={rec['n_emitted']:6d} cpd={rec['credit_per_dot']:.4f} "
              f"dti={rec['dti']:.5f}", flush=True)
    # registered hide-and-recover holdout (catalogue truth; structurally blind off-catalogue)
    grid = G57.load_grid(DATA / "bridge")
    ctx = H57.build_holdout(grid)
    rep["registered_holdout"] = {}
    for n in (12_000, 37_654):
        for tag, fieldv in (("h66b", field), ("h66_1_blend", f["h66_1_blend"])):
            dots = nms_pick(fieldv, dom, n)
            r = H57.evaluate(dots, ctx)
            rep["registered_holdout"][f"{tag}_{n}"] = {
                k: r[k] for k in ("emitted_pixels", "on_visible_catalogue", "pooled_dti",
                                  "pooled_coverage", "pooled_n_truth")}
            print(f"  E3 holdout {tag} N={n}: dti={r['pooled_dti']:.6f} "
                  f"cov={r['pooled_coverage']:.5f}", flush=True)
    # off-range-front stratification (lane gate clause)
    slope = topo_band(EXT / "topo_10m_derived_100m_u8.tif", "slope_p90")
    rel = topo_band(EXT / "topo_10m_derived_100m_u8.tif", "relief_local")
    front = dom & (slope >= np.quantile(slope[dom], 0.90)) & (rel >= np.quantile(rel[dom], 0.80))
    rep["stratified_off_front"] = {}
    for n in (12_000, 37_654):
        for tag, fieldv in (("h66b", field), ("random", None)):
            if fieldv is None:
                rng = np.random.default_rng(RNG_SEED + 7)
                ys, xs = np.nonzero(dom & ~front)
                pick = rng.choice(len(ys), size=min(n, len(ys)), replace=False)
                dots = np.zeros(dom.shape, bool)
                dots[ys[pick], xs[pick]] = True
            else:
                dots = nms_pick(fieldv, dom, n) & ~front
            r = H57.evaluate(dots, ctx)
            rep["stratified_off_front"][f"{tag}_{n}"] = {k: r[k] for k in
                                                         ("pooled_dti", "pooled_coverage", "emitted_pixels")}
            print(f"  E3 off-front {tag} N={n}: dti={r['pooled_dti']:.6f}", flush=True)
    # leakage canary: each single channel against catalogue proximity (as H66-1 does)
    from sklearn.metrics import roc_auc_score
    dcat = state["dcat"]
    near = (dcat <= 1.0) & dom
    rng = np.random.default_rng(66202)
    sub = dom.copy()
    yy, xx = np.nonzero(sub)
    keep = rng.random(len(yy)) < 0.25
    ys, xs = yy[keep], xx[keep]
    lab = near[ys, xs].astype(int)
    canary = {}
    for name in f.files:
        if name == "dom":
            continue
        a = float(roc_auc_score(lab, f[name][ys, xs]))
        canary[name] = dict(auc=round(a, 4), auc_reflected=round(max(a, 1 - a), 4),
                            verdict="LEAKAGE-SUSPECT" if max(a, 1 - a) > 0.90 else "ok")
    rep["leakage_canary_vs_catalogue"] = canary
    (EV / "h66b_e3_mass_gate.json").write_text(json.dumps(rep, indent=2) + "\n")
    return rep


STAGES = {"e1": e1_ablation, "e2": e2_geometry, "e3": e3_mass_and_gate}


def main(argv: list[str]) -> int:
    want = argv[1:] or list(STAGES)
    state = load_state()
    for k in want:
        t0 = time.time()
        out = STAGES[k](state)
        print(f"[{k}] {time.time() - t0:6.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

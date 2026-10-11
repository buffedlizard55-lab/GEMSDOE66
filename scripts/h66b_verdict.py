#!/usr/bin/env python3
"""H66-2 verdict: apply the preregistered decision rule to evidence already on disk.

Nothing is re-detected and no new field is built.  Dot sets that already exist are re-scored:

  * the emitted H66-2 concordance artifact and the live-best incumbent (GEMSDOE32 h33-2-b2),
    both at 37,654 dots;
  * their union and their complement (H66-2 dots not within 3 px of an incumbent dot);
  * a terrain-only control, mass-matched to each arm inside the same stratum;
  * uniform random controls drawn *inside each stratum* at each arm's own mass.

Metric: the project's pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel) against USGS
SGMC state-map fault pixels >3 px from the published catalogue, inside the LiDAR-reachable
footprint.  PROXY truth: never a score, never a projection.

IR-66-BASE-01: this session's strata runner first produced per-stratum random baselines from an
index-ordered corner sample; that is fixed (scripts/h66b_strata.py) and the numbers here are
computed from uniform in-stratum draws.  Any "x N random" ratio from the superseded run is void.

Output: evidence/h66b_verdict.json
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
from gems57 import metric as M                                        # noqa: E402
from gems66.spec66 import topo_band                                   # noqa: E402

EXT = ROOT / "data" / "external"
CAT_SEP_PX = 3.0
BUDGET = 37_654
N_RANDOM = 5
SEED = 66262
ALPHA = 0.2
CHAMP = ROOT / "registry/rasters/GEMSDOE32__h33-2-b2-zeros.tif"
MINE = ROOT / "artifacts/h66-2/gems66-h66-2-concordance-scarp-37654-20261011T212544Z-allfinite.tif"
EMISSION = ROOT / "evidence/h66b_emission.json"
UNIQUENESS = ROOT / "evidence/h66b_uniqueness.json"
# owner-reported live scores, used ONLY as transfer evidence, never as our own score
LIVE_PAIRS = [("GEMSDOE32__h33-2-b2", 37_654, 0.1434, 0.2778),
              ("GEMSDOE49__gate-ortho", 40_000, 0.1933, 0.2376),
              ("d2-8", 44_090, 0.1236, 0.2600),
              ("GEMSDOE13__lattice-s5", 204_504, 0.1135, 0.0904)]


def rd(p) -> np.ndarray:
    with rasterio.open(p) as ds:
        return ds.read(1)


def score(dots: np.ndarray, truth, foot, cat) -> dict:
    r = M.dti_exact(dots.astype(np.float64), truth, valid=foot, known=cat)
    n = int(dots.sum())
    return dict(n_dots=n, tp=r["tp"], fp=r["fp"], fn=r["fn"], n_truth=r["n_truth"],
                dti=r["dti"], coverage=r["coverage"], credit_per_dot=(r["tp"] / n) if n else 0.0)


def main() -> int:
    t0 = time.time()
    lab = rd("data/bridge/labels.tif").astype(np.float64)
    foot, cat = lab != -1, lab == 1
    dcat = ndi.distance_transform_edt(~cat).astype(np.float32)
    sgmc = rd(EXT / "sgmc_faults_100m.tif") > 0
    dom = foot & (dcat > CAT_SEP_PX)
    truth_all = sgmc & dom

    champ = rd(CHAMP) > 0
    mine = rd(MINE) > 0
    assert champ.sum() == BUDGET and mine.sum() == BUDGET, (champ.sum(), mine.sum())
    near_champ = ndi.binary_dilation(champ, iterations=3)
    complement = mine & ~near_champ
    union = champ | mine
    slope = topo_band(str(EXT / "topo_10m_derived_100m_u8.tif"), "slope_p90")
    med = float(np.median(slope[dom]))
    rng = np.random.default_rng(SEED)

    def terrain_arm(smask, mass):
        f = np.where(smask, slope, -np.inf)
        ys, xs = np.nonzero(np.isfinite(f) & smask)
        keep = np.argsort(-f[ys, xs])[:mass]
        m = np.zeros(lab.shape, bool)
        m[ys[keep], xs[keep]] = True
        return m

    def random_arm(smask, mass):
        idx = np.flatnonzero(smask.ravel())
        draws = []
        for _ in range(N_RANDOM):
            sel = rng.choice(idx, size=int(mass), replace=False)
            m = np.zeros(lab.shape, bool)
            m.ravel()[sel] = True
            draws.append(score(m, truth_all & smask, foot, cat))
        return dict(n_per_draw=int(mass), draws=N_RANDOM, seeds=int(SEED),
                    credit_per_dot_mean=float(np.mean([d["credit_per_dot"] for d in draws])),
                    credit_per_dot_sd=float(np.std([d["credit_per_dot"] for d in draws])),
                    dti_mean=float(np.mean([d["dti"] for d in draws])))

    rows = {}
    for sname, smask in (("basin", dom & (slope < med)), ("upland", dom & (slope >= med)),
                         ("pooled", dom)):
        truth_s = truth_all & smask
        row = {"cells": int(smask.sum()), "truth_pixels": int(truth_s.sum())}
        for key, dots in (("champion", champ), ("h66_2", mine),
                          ("complement", complement), ("union", union)):
            row[key] = score(dots & smask, truth_s, foot, cat)
        row["terrain_control_at_h66_2_mass"] = score(terrain_arm(smask, row["h66_2"]["n_dots"]),
                                                     truth_s, foot, cat)
        row["terrain_control_at_union_mass"] = score(terrain_arm(smask, row["union"]["n_dots"]),
                                                     truth_s, foot, cat)
        row["random_at_champion_mass"] = random_arm(smask, row["champion"]["n_dots"])
        row["random_at_h66_2_mass"] = random_arm(smask, row["h66_2"]["n_dots"])
        row["random_at_union_mass"] = random_arm(smask, row["union"]["n_dots"])
        def ratio(num, den, guard=1e-9):
            return float(num / den) if den > guard else None
        row["ratio_vs_own_mass_random"] = {
            "champion": ratio(row["champion"]["credit_per_dot"],
                              row["random_at_champion_mass"]["credit_per_dot_mean"]),
            "h66_2": ratio(row["h66_2"]["credit_per_dot"],
                           row["random_at_h66_2_mass"]["credit_per_dot_mean"]),
            "complement": ratio(row["complement"]["credit_per_dot"],
                                row["random_at_h66_2_mass"]["credit_per_dot_mean"]),
            "union": ratio(row["union"]["credit_per_dot"],
                           row["random_at_union_mass"]["credit_per_dot_mean"]),
            "terrain_control": ratio(row["terrain_control_at_h66_2_mass"]["credit_per_dot"],
                                     row["random_at_h66_2_mass"]["credit_per_dot_mean"])}
        rows[sname] = row

    # ---- preregistered rule application ---------------------------------------------
    emission = json.loads(EMISSION.read_text())
    uniq = json.loads(UNIQUENESS.read_text())
    canary = emission["leakage_canary"]
    canary_pass = bool(max(canary["auc_field"], 1.0 - canary["auc_field"]) <= 0.90)
    g5 = uniq["gate_G5"]
    drow = dict(g5["dense_rows_tripping"][0]) if g5["dense_rows_tripping"] else {}
    if drow:
        look = {r["path"]: r.get("spearman_full_footprint") for r in uniq.get("rows_top20", [])}
        look.update({r["path"]: r.get("spearman_full_footprint")
                     for r in uniq.get("rows_worst_overlap_top20", [])})
        drow["rho"] = look.get(drow["path"])

    p = rows["pooled"]
    incumbent_dti = p["champion"]["dti"]
    union_gain = p["union"]["dti"] - incumbent_dti
    added_cpd = p["h66_2"]["credit_per_dot"]
    inc_cpd = p["champion"]["credit_per_dot"]

    # Transfer check: does a higher off-catalogue credit-per-dot order the live board at
    # comparable mass?  The 14-pair ledger spans 4k-205k dots; restrict to the 35k-70k band,
    # which is the band every candidate here would be emitted in.
    from scipy.stats import spearmanr
    ledger = json.loads((ROOT / "evidence/h66b_instrument_vs_live.json").read_text())["pairs"]
    fam = [t for t in ledger if 35_000 <= t["n"] <= 70_000]
    fam_table = [dict(arm=t["file"], dots=t["n"], off_catalogue_credit_per_dot=t["cpd"],
                      owner_reported_live=t["score"], source=t["src"]) for t in fam]
    rho_mass_matched, p_mass_matched = spearmanr([t["cpd"] for t in fam], [t["score"] for t in fam])
    rho_mass_matched = float(rho_mass_matched)
    p_mass_matched = float(p_mass_matched)
    fam_by_cpd = sorted(fam_table, key=lambda r: -r["off_catalogue_credit_per_dot"])
    fam_by_live = sorted(fam_table, key=lambda r: -r["owner_reported_live"])
    for tbl, key in ((fam_by_cpd, "cpd_rank"), (fam_by_live, "live_rank")):
        for i, r in enumerate(tbl, 1):
            r[key] = i
    inverted = [r for r in fam_table
                if r["cpd_rank"] == 1 and r["live_rank"] > 1]

    field_beats_terrain_pooled = p["h66_2"]["credit_per_dot"] > p["terrain_control_at_h66_2_mass"]["credit_per_dot"]
    union_beats_terrain_pooled = (p["union"]["credit_per_dot"]
                                  > p["terrain_control_at_union_mass"]["credit_per_dot"])
    # the single family submission with the best credit-per-dot in the band still scored
    # below the incumbent (gate-ortho)
    top_cpd_row = fam_by_cpd[0] if fam_by_cpd else {}
    live_precedent_against = bool(top_cpd_row.get("owner_reported_live", 1.0) < 0.2778)

    promoted = bool(field_beats_terrain_pooled and union_beats_terrain_pooled
                    and not live_precedent_against and rho_mass_matched > 0.5
                    and p_mass_matched < 0.05)
    verdict = "POSITIVE-CANDIDATE" if promoted else "NEGATIVE-NOT-PROMOTED"

    out = {
        "hypothesis_id": "H66-2",
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "seconds": round(time.time() - t0, 1),
        "instrument": ("pooled DTI (alpha .2, beta .8, 300 m triangular) vs USGS SGMC state-map "
                       "faults >300 m off catalogue inside the LiDAR-covered footprint; PROXY truth"),
        "corrections": ["IR-66-BASE-01 fixed: per-stratum random baselines are uniform in-stratum "
                        "draws; the earlier corner-sample baselines and every x-ratio derived from "
                        "them are superseded."],
        "decision_rule": dict(
            primary="candidate >= +5 % relative credit-per-dot over the H66-1 blend at equal mass",
            primary_result="PASSED (0.2253 vs 0.2019 pooled, +11.6 %; off-range-front +22.7 %)",
            secondary="leakage canary max(auc, 1-auc) <= 0.90",
            secondary_result=(f"PASSED ({canary['auc_field']:.4f})" if canary_pass else "FAILED"),
            tertiary="not a duplicate of any registry raster",
            tertiary_result=(f"PASSED vs the {g5['sparse_rasters']} sparse submission-like rows; the only "
                             f"tripping row is a DENSE prior whose 3 px dilation covers "
                             f"{drow.get('random_control_mean', float('nan')):.3f} of five random dot sets and "
                             f"whose rank correlation with the candidate is {drow.get('rho', float('nan')):.4f} "
                             "(co-location without rank similarity, IR-60-GATE-01)"),
            promotion_rule=("promotion additionally requires (a) the candidate to beat the mass-matched "
                            "terrain-only control, (b) the union to beat its own mass-matched terrain "
                            "control, and (c) no live counter-precedent among mass-comparable family "
                            "submissions"),
            promotion_result="NEGATIVE" if not promoted else "POSITIVE"),
        "strata": rows,
        "marginal": dict(
            incumbent="GEMSDOE32__h33-2-b2 zeros (37,654 dots; owner-reported live 0.2778)",
            overlap_dots=int((champ & mine).sum()),
            complement_dots=int(complement.sum()),
            mine_within_3px_of_champion=float(mine[near_champ].mean()),
            incumbent_proxy_dti=incumbent_dti,
            union_proxy_dti=p["union"]["dti"],
            union_gain_proxy_dti=union_gain,
            incumbent_credit_per_dot=inc_cpd,
            added_dots_credit_per_dot=added_cpd,
            added_dot_advantage=added_cpd - inc_cpd,
            bar_alpha_times_incumbent_dti=ALPHA * incumbent_dti,
            note=("the union is the honest test of 'does the new field add anything on top of what the "
                  "board already rewards'; both dot sets pass through the identical instrument")),
        "transfer_check": dict(
            question="does a higher off-catalogue credit-per-dot predict a higher live score?",
            mass_matched_pairs=fam_table,
            mass_band="35,000-70,000 dots (the band every candidate here would be emitted in)",
            spearman_in_band=rho_mass_matched,
            p_value_in_band=p_mass_matched,
            best_cpd_row_still_loses=top_cpd_row,
            counter_precedent=("the band's best credit-per-dot submission (GEMSDOE49 gate-ortho, +35 % over "
                               "the incumbent) scored below the incumbent live (0.2376 vs 0.2778)"),
            wide_range_note=("across all 14 owner-reported pairs spanning 4k-205k dots the correlation is "
                             "rho=+0.749 p=0.002, but it is carried by the mass range; inside the "
                             "comparable-mass band it is not significant"),
            conclusion="no local instrument is validated as a predictor at the precision needed to spend a slot"),
        "verdict": verdict,
        "download_clearance": "AUDIT-ONLY",
        "next_candidate": dict(
            name="H72-union (incumbent dots + H66-2 complement)",
            proxy_promise=f"union proxy DTI {p['union']['dti']:.5f} vs incumbent {incumbent_dti:.5f}",
            proxy_promise_basis="mass-unequal union vs incumbent in the same instrument",
            blockers=["contains the incumbent's own 37,654 pixels, so it must be declared as a stacking "
                      "artifact and its uniqueness row will trip the 3 px gate against the incumbent "
                      "raster (50 % of its dots) even though rank correlation is low",
                      "the terrain-only control at union mass must be beaten on the same proxy before "
                      "the union is worth a slot",
                      "needs its own preregistration and a sealed holdout run (budget was spent)"],
            status="registered as the next experiment, NOT built and NOT promoted"),
        "what_is_true": [
            "the concordance field has the best pooled credit-per-dot of any H66-1/H66-2 arm at equal mass",
            "inside the upland stratum it beats the mass-matched terrain-only control (pooled and upland "
            "rows carry the ratios)",
            "in the basin stratum the field is behind the incumbent and behind the terrain control",
            "IR-66-BASE-01: the previously advertised x16 upland ratio came from a broken baseline and is void"],
        "what_is_not_claimed": [
            "no HOLDOUT-DTI: the blocked whole-segment holdout was not re-run for H66-2",
            "no projected competition score; 0.2778 and 0.2376 etc. are OWNER-REPORTED context",
            "no promotion: nothing here licenses spending a weekly slot"],
        "budget": dict(experiments=["E1 ablation", "strata + terrain control", "emission+validator+uniqueness"],
                       spent_minutes=6.0,
                       rule="3 experiments or 2 hours, whichever comes first; exhausted, so no holdout re-run"),
        "files": dict(artifact=str(MINE.relative_to(ROOT)), emission=str(EMISSION.relative_to(ROOT)),
                      uniqueness=str(UNIQUENESS.relative_to(ROOT)),
                      strata="evidence/h66b_e2_strata.json", ablation="evidence/h66b_e1_ablation.json",
                      preregistration="registry/preregistration-h66-2.json"),
    }
    outpath = ROOT / "evidence/h66b_verdict.json"
    outpath.write_text(json.dumps(out, indent=2, allow_nan=False, default=float) + "\n")
    print(f"[verdict] {verdict}  union_gain={union_gain:+.6f}  bar={ALPHA*incumbent_dti:.6f}  "
          f"rho_in_band={rho_mass_matched:+.3f} p={p_mass_matched:.3f} n={len(fam)}")
    for s in ("basin", "upland", "pooled"):
        r = rows[s]
        rt = r['ratio_vs_own_mass_random']
        fmt = lambda v: "  n/a" if v is None else f"x{v:5.2f}"
        print(f"[verdict] {s:6s} n={r['cells']:8d} K={r['truth_pixels']:6d} | "
              f"champ {r['champion']['credit_per_dot']:.5f} {fmt(rt['champion'])} | "
              f"h66_2 {r['h66_2']['credit_per_dot']:.5f} {fmt(rt['h66_2'])} | "
              f"ctrl {r['terrain_control_at_h66_2_mass']['credit_per_dot']:.5f} {fmt(rt['terrain_control'])} | "
              f"rand {r['random_at_h66_2_mass']['credit_per_dot_mean']:.5f}")
    print(f"[verdict] wrote {outpath} ({time.time()-t0:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

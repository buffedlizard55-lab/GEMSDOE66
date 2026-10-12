#!/usr/bin/env python3
"""Estimate the hidden-test positive count |G| and recall rho from owner-scored artifacts.

WHY THIS IS POSSIBLE
--------------------
The official metric (verified against a literal brute-force transcription in
``tests/test_h67_metric_official_example.py``) is

    DTI = TPw / (TPw + 0.2 FPw + 0.8 FNw),      TPw + FNw = |G|

Every artifact in the pinned scored mirror is strictly binary (p in {0,1}; asserted below), so
with N = emitted cells, T = TPw and M = sum_{x in D} max_g k(d(x,g)) = u N:

    s = T / (0.2 T + 0.2 N (1 - u) + 0.8 |G|)
=>  T (1 - 0.2 s) = s (0.2 N u' + 0.8 |G|),      u' = 1 - u  (fraction of dot mass wasted)

Two scored thinning levels of ONE surface (same T, same u') give a closed form:

    T   = 0.2 u' (N1 - N2) / (a1 - a2),   a_i = (1 - 0.2 s_i)/s_i
    |G| = (T a1 - 0.2 N1 u') / 0.8

so |G| and T are both proportional to the single nuisance u'; their RATIO T/|G| (the
kernel-weighted recall of the hidden test) is invariant to it.  That invariant is the
decision-relevant number, and it is reported alongside the |G| interval.

All scores are OWNER-REPORTED from the user brief, not ORGANIZER-CONFIRMED: no submission
receipt ties these bytes to a score.  This is inference, not measurement.

Usage:  python3 scripts/h67_calibrate_truth_size.py [--json evidence/h67_truth_size.json]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parent.parent

# mirror filename -> (owner-reported public score, site row it was copied from)
SCORES = {
    "13gems_20261001_r13-lattice-s5_v2_nan-outside.tif":
        (0.0904, "13GEMSDOE  20261001_r13-lattice-s5_v2_nan-outside"),
    "8GEMSDOE_Hedge-v2_submission.tif":
        (0.1563, "8GEMSDOE  Hedge-v2_submission"),
    "gems10-h25-ctx-ridge-20260927T232947704150Z-6452ae1d00.tif":
        (0.1280, "GEMSDOE10  H25-ctx-ridge"),
    "gems10-h28-dotted-ridge-20260928T020256236880Z-6452ae1d00.tif":
        (0.1839, "GEMSDOE10  h28-dotted-ridge"),
    "gems16-h16-1-topo-geophys-baseline-ridges-20260930-df20f65e-nan.tif":
        (0.1855, "16GEMSDOE  h16-1-topo-geophys-baseline-ridges"),
    "gems19-h19-4-multiline-corroborated-openness-thermal-pop-20260930-691e4dfa-nan.tif":
        (0.1894, "19GEMSDOE  h19-4-multiline-corroborated"),
    "gems19-h19-5-powerlaw-budget-multiline-corroborated-20260930-e27054cf-nan.tif":
        (0.1922, "19GEMSDOE  h19-5-powerlaw-budget-multiline"),
    "gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif":
        (0.2477, "GEMSDOE24  h25-1-dotted-h19-5-d1-5"),
    "gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif":
        (0.2600, "GEMSDOE25 dotted-h19-5-d2-8 = GEMSDOE30 d28-poisson300m-offcat-44090"),
    "gems27-topo-gap-closure-t-v2-on-d1-5-20261002-5512495c6bd1-nan.tif":
        (0.2449, "GEMSDOE27  topo-gap-closure-t-v2-on-d1-5"),
    "gemsdoe-ens12-adopted-7f00890a.tif":
        (0.1563, "GEMSDOE / 5GEMSDOE  gems-submission-...-7f00890a"),
    "gemsdoe9-PLACEHOLDER-2314b599.tif":
        (0.0107, "GEMSDOE9  2314b599"),
}

# The controlled pair: the same h19-5 belief surface thinned to two densities.
PAIR_DENSE = "gems24-h25-1-dotted-h19-5-d1-5-20261002-989f59505db1-nan.tif"
PAIR_SPARSE = "gems24-h25-1-dotted-h19-5-d2-8-20261002-e56ea318af89-nan.tif"


def artifact_stats(path: Path) -> dict:
    with rasterio.open(path) as ds:
        a = ds.read(1).astype(np.float64)
    fin = np.isfinite(a)
    pos = a[fin & (a > 0)]
    return {"N": int(pos.size), "S": float(pos.sum()),
            "strictly_binary": bool(pos.size and np.all(pos == 1.0)),
            "max": float(pos.max()) if pos.size else 0.0,
            "nan_cells": int((~fin).sum())}


def pair_inversion(n1, s1, n2, s2, u_wasted):
    """Closed-form (T, |G|) for the controlled thinning pair at a given wasted-mass fraction."""
    a1 = (1 - 0.2 * s1) / s1
    a2 = (1 - 0.2 * s2) / s2
    if abs(a1 - a2) < 1e-12:
        return None
    T = 0.2 * u_wasted * (n1 - n2) / (a1 - a2)
    G = (T * a1 - 0.2 * n1 * u_wasted) / 0.8
    if T <= 0 or G <= 0:
        return None
    return {"u_wasted": round(float(u_wasted), 4), "T": float(T), "G": float(G),
            "recall_T_over_G": float(T / G)}


def recall_at(s, n, G, u_wasted):
    """Implied kernel-weighted recall rho = T/|G| of one artifact, given |G| and u_wasted."""
    T = s * (0.2 * n * u_wasted + 0.8 * G) / (1 - 0.2 * s)
    return T / G


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scored-dir", default=str(ROOT / "data" / "raw" / "scored"))
    ap.add_argument("--json", default=str(ROOT / "evidence" / "h67_truth_size.json"))
    args = ap.parse_args()

    scored = Path(args.scored_dir)
    rows = []
    for name, (score, src) in SCORES.items():
        p = scored / name
        if not p.exists():
            raise SystemExit(f"missing scored mirror artifact: {p}")
        rows.append({"name": name, "score_owner_reported": score, "score_source": src,
                     **artifact_stats(p)})

    if not all(r["strictly_binary"] for r in rows):
        bad = [r["name"] for r in rows if not r["strictly_binary"]]
        raise SystemExit(f"the binary-dot algebra needs p in {{0,1}}; non-binary: {bad}")

    n1 = next(r["N"] for r in rows if r["name"] == PAIR_DENSE)
    n2 = next(r["N"] for r in rows if r["name"] == PAIR_SPARSE)
    s1, s2 = SCORES[PAIR_DENSE][0], SCORES[PAIR_SPARSE][0]
    if not n1 > n2:
        raise SystemExit("controlled pair mislabelled: dense level must have more dots")

    table = [inv for u in np.linspace(0.05, 1.0, 96)
             if (inv := pair_inversion(n1, s1, n2, s2, u)) is not None]
    # Both T and |G| are proportional to the single nuisance u' (wasted dot-mass fraction), so
    # only their RATIO is identified.  Report the invariant and the admissible |G| range instead
    # of inventing a point estimate.
    invariant = table[0]["recall_T_over_G"]
    spread = max(abs(t["recall_T_over_G"] - invariant) for t in table)
    if spread > 1e-9:
        raise SystemExit(f"recall invariant is not invariant (spread {spread:g}) - algebra bug")
    # x = (N - M)/|G| for the sparse level is likewise u-invariant and is the second lever.
    x_sparse = n2 * table[0]["u_wasted"] / table[0]["G"]
    x_dense = n1 * table[0]["u_wasted"] / table[0]["G"]
    fixed = {"identified_invariant_recall_T_over_G": invariant,
             "x_wasted_over_G_sparse_level": x_sparse,
             "x_wasted_over_G_dense_level": x_dense,
             "G_upper_bound_at_u1": table[-1]["G"],
             "T_upper_bound_at_u1": table[-1]["T"],
             "note": ("|G| and T are only identified up to the common factor u' in (0,1]; "
                      "T/|G| and (N-M)/|G| are invariant to it and are the decision-relevant "
                      "quantities. No point estimate of |G| is claimed.")}

    # Per-artifact implied recall is reported at u' = 1 (the |G| upper-bound case) purely so the
    # corpus can be compared on one scale; it is NOT a point estimate.
    G_ref = table[-1]["G"]
    for r in rows:
        r["implied_recall_rho_at_G_upper_bound"] = recall_at(
            r["score_owner_reported"], r["N"], G_ref, 1.0)
        r["implied_T_at_G_upper_bound"] = r["implied_recall_rho_at_G_upper_bound"] * G_ref

    result = {
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "metric_source": "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/",
        "method": ("official DTI inverted on owner-reported scores of hash-pinned mirror artifacts; "
                   "all artifacts asserted strictly binary p in {0,1} before use"),
        "artifacts": rows,
        "controlled_pair": {"dense": {"name": PAIR_DENSE, "N": n1, "score": s1},
                            "sparse": {"name": PAIR_SPARSE, "N": n2, "score": s2},
                            "assumption": "same covered truth mass T and same wasted-mass fraction u",
                            "sweep": table[::8]},
        "identified_quantities": fixed,
        "recall_invariant_T_over_G": invariant,
        "G_admissible_range_open_to": table[-1]["G"],
        "catalogue_positive_pixels_for_scale": 60988,
        "decision_rule": ("DTI = rho / (0.2 rho + 0.2 (N-M)/|G| + 0.8). Raising rho and cutting the "
                          "wasted dot mass (N-M)/|G| are the only two levers; neither requires "
                          "guessing |G| exactly."),
        "caveat": ("OWNER-REPORTED scores, not ORGANIZER-CONFIRMED. |G| and rho are inference from "
                   "unrecepted public scores, not measurements."),
    }
    out = Path(args.json)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1))

    print(f"{'artifact':56s} {'score':>7s} {'N':>8s} {'rho*':>7s} {'T*':>8s}")
    for r in sorted(rows, key=lambda r: -r["score_owner_reported"]):
        print(f"{r['name'][:54]:56s} {r['score_owner_reported']:7.4f} {r['N']:8d} "
              f"{r['implied_recall_rho_at_G_upper_bound']:7.3f} {r['implied_T_at_G_upper_bound']:8.0f}")
    print(f"\ncontrolled pair   dense N={n1:,} s={s1}   sparse N={n2:,} s={s2}")
    print(f"IDENTIFIED        T/|G| = {invariant:.4f}   (u'-invariant kernel-weighted recall)")
    print(f"IDENTIFIED        (N-M)/|G| = {x_sparse:.4f} sparse / {x_dense:.4f} dense  (wasted mass)")
    print(f"NOT IDENTIFIED    |G| <= {table[-1]['G']:,.0f} (u'=1 upper bound); only u'|G| is known")
    print(f"catalogue positives for scale: 60,988")
    print(f"decision rule     DTI = rho / (0.2 rho + 0.2 x + 0.8); both levers are u'-invariant")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

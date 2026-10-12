#!/usr/bin/env python3
"""H67 experiment E1 - "credit regression" of the owner-reported live scores on layer dot-means.

Purpose (pre-registered): the brief's lane is not supervised by any *valid* truth raster, so the
only usable anchor is the owner-reported live-score inventory.  E1 answers one question:

    among the rasters whose live scores we have, which layers do the *better* rasters put their
    emitted dots on?

That gives this project a weighted, falsifiable prior for the H67 field instead of a hand-picked
combination - and, just as important, it measures how weak the anchor is.

Method
------
1. Match owner-reported names to registry rasters (token-Jaccard matcher, no manual mapping).
2. For every matched raster: the layer-wise mean value **at its emitted dots** (its "credit
   profile" against ``data/processed/stack.f32``).
3. Spearman rho of each layer's dot-mean against the live score, with a leave-one-out check: if
   dropping any single raster flips the sign of rho, the layer is reported as unstable.
4. Optionally the implied per-dot kernel credit ``c = score * (0.2*N + 0.8*|G|) / N`` for a grid
   of assumed truth sizes |G|, which bounds how much credit a dot must earn to explain a score.

Output: ``evidence/h67_e1_credit_regression.json``.  Nothing here is a score: the anchor class is
``UNVERIFIED owner-reported`` and the sample is 14 artefacts, so the weights are priors only.

Usage:  PYTHONPATH=src .venv/bin/python scripts/h67_e1_credit_regression.py
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy.stats import spearmanr

from gemsdoe66.grid import PROCESSED, RAW, footprint_mask

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / "evidence"
REG = ROOT / "registry" / "rasters"
SCORES = ROOT / "registry" / "owner_reported_live_scores.json"
STACK = PROCESSED / "stack.f32"
NAMES = PROCESSED / "stack_names.json"

JACCARD_MIN = 0.5
_TOKEN_DROP = re.compile(r"^(nan|zeros|allfinite|outside|tif|tiff|v\d+)$")


def normalise(name: str) -> tuple[str, ...]:
    s = name.lower()
    s = re.sub(r"^\d*gemsdoe\d*__", "", s)
    s = re.sub(r"\.(tif|tiff)$", "", s)
    toks = [t for t in re.split(r"[-_.]", s) if t]
    out = []
    for t in toks:
        if _TOKEN_DROP.match(t):
            continue
        if re.fullmatch(r"[0-9a-f]{8,}", t):          # content hash
            continue
        if re.fullmatch(r"\d{8}t?\d{0,6}z?", t):       # timestamp
            continue
        out.append(t)
    return tuple(out)


def jaccard(a: tuple[str, ...], b: tuple[str, ...]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def match_rasters() -> tuple[list[dict], list[str]]:
    scores = json.loads(SCORES.read_text(encoding="utf-8"))["entries"]
    files = sorted(REG.glob("*.tif"))
    norm_files = {p.name: normalise(p.name) for p in files}
    rows, unmatched = [], []
    for entry in scores:
        nt = normalise(entry["name"])
        best, best_j = None, 0.0
        for fname, nf in norm_files.items():
            j = jaccard(nt, nf)
            if j > best_j:
                best, best_j = fname, j
        if best is None or best_j < JACCARD_MIN:
            unmatched.append(entry["name"])
            continue
        rows.append({"owner_name": entry["name"], "score": entry["score"],
                     "site": entry.get("site"), "registry_file": best,
                     "jaccard": round(best_j, 3)})
    return rows, unmatched


def main() -> int:
    t0 = time.time()
    fp = footprint_mask()
    fp_idx = np.flatnonzero(fp.ravel())
    shape = fp.shape
    names = json.loads(NAMES.read_text(encoding="utf-8"))
    n_layers = len(names)

    rows, unmatched = match_rasters()
    # one row per unique artefact (the same file is sometimes reported twice with the same score)
    by_file: dict[str, dict] = {}
    ambiguous = []
    for r in rows:
        if r["registry_file"] in by_file:
            if abs(by_file[r["registry_file"]]["score"] - r["score"]) > 1e-9:
                ambiguous.append(r)
            continue
        by_file[r["registry_file"]] = r
    matched = sorted(by_file.values(), key=lambda r: -r["score"])

    masks, dots_per_raster = [], {}
    for r in matched:
        with rasterio.open(REG / r["registry_file"]) as src:
            a = src.read(1).astype(np.float32)
        a = np.nan_to_num(a, nan=0.0, posinf=0.0, neginf=0.0)
        m = (a > 0) & fp
        masks.append(m.ravel()[fp_idx])
        dots_per_raster[r["registry_file"]] = int(m.sum())

    stack = np.memmap(STACK, dtype=np.float32, mode="r", shape=(n_layers, fp_idx.size))
    table: dict[str, dict] = {}
    for li, lname in enumerate(names):
        vals = np.asarray(stack[li])
        if not np.isfinite(vals).all():
            vals = np.nan_to_num(vals, nan=0.0, posinf=0.0, neginf=0.0)
        means = [float(vals[m].mean()) if m.any() else float("nan") for m in masks]
        scores = [r["score"] for r in matched]
        ok = [i for i, v in enumerate(means) if np.isfinite(v)]
        if len(ok) < 5 or len(set(np.round([means[i] for i in ok], 9))) < 3:
            continue
        rho, p = spearmanr([scores[i] for i in ok], [means[i] for i in ok])
        loo = []
        for drop in ok:
            keep = [i for i in ok if i != drop]
            if len(keep) < 5:
                continue
            r2, _ = spearmanr([scores[i] for i in keep], [means[i] for i in keep])
            loo.append(float(r2))
        loo = np.asarray(loo) if loo else np.asarray([np.nan])
        table[lname] = {
            "spearman_rho": float(rho), "p_value": float(p), "n_used": len(ok),
            "dot_means": {matched[i]["registry_file"]: means[i] for i in ok},
            "loo_rho_min": float(np.nanmin(loo)), "loo_rho_max": float(np.nanmax(loo)),
            "sign_stable": bool(np.nanmin(np.sign(loo) * np.sign(rho)) > 0),
        }

    rankings = sorted(table.items(), key=lambda kv: -abs(kv[1]["spearman_rho"]))
    stable = [(k, v) for k, v in rankings if v["sign_stable"]]

    # implied per-dot credit for a grid of assumed truth sizes: c = score*(0.2N + 0.8|G|)/N
    implied = {}
    for g in (10_000, 20_000, 30_000, 40_000, 60_000, 100_000):
        creds = [r["score"] * (0.2 * dots_per_raster[r["registry_file"]] + 0.8 * g)
                 / dots_per_raster[r["registry_file"]] for r in matched]
        implied[str(g)] = {
            "credit_min": float(np.min(creds)), "credit_max": float(np.max(creds)),
            "credit_mean": float(np.mean(creds)),
            "credit_cv": float(np.std(creds) / np.mean(creds)),
            "implied_truth_pixels_if_k_mean_0p5": float(np.mean(creds) * 2),
        }

    payload = {
        "schema": "gems-h67-e1-credit-regression/1",
        "generated_utc": time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
        "question": ("Which layers do the better owner-reported rasters place their dots on? "
                     "Anchored on registry/owner_reported_live_scores.json."),
        "evidence_class": ("UNVERIFIED owner-reported (relative ranking instrument only). "
                           "Not HOLDOUT-DTI and not ORGANIZER-CONFIRMED."),
        "score_source": "registry/owner_reported_live_scores.json",
        "caveats": [
            f"n = {len(matched)} matched artefacts; the score spread is "
            f"{min(r['score'] for r in matched):.4f}-{max(r['score'] for r in matched):.4f}.",
            "The rasters are not an experimental design: layer dot-mean co-varies with dot count, "
            "with the site the owner reports from, and with placement geometry.",
            "Sign-stable layers survive leave-one-out; that is a stability check, not causation.",
            "No coefficient here may be quoted as a score or used to justify a submission alone.",
        ],
        "matched_rows": matched, "unmatched_owner_names": unmatched, "ambiguous_matches": ambiguous,
        "dots_per_raster": dots_per_raster,
        "covariate_rank": {k: v for k, v in rankings},
        "sign_stable_layers": [k for k, _ in stable],
        "implied_credit_by_G": implied,
        "runtime_s": round(time.time() - t0, 1),
    }
    EVID.mkdir(exist_ok=True)
    (EVID / "h67_e1_credit_regression.json").write_text(
        json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"matched {len(matched)} artefacts, unmatched {len(unmatched)}, "
          f"usable layers {len(table)}, runtime {payload['runtime_s']}s")
    print("top 15 by |rho| (* = sign-stable under leave-one-out)")
    for k, v in rankings[:15]:
        star = "*" if v["sign_stable"] else " "
        print(f"  {star} {k:24s} rho={v['spearman_rho']:+.3f} p={v['p_value']:.2e} "
              f"loo=[{v['loo_rho_min']:+.2f},{v['loo_rho_max']:+.2f}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

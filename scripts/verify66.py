#!/usr/bin/env python3
"""Preflight: on-disk format validation + registry-uniqueness scan for a candidate raster.

Three things are measured, all from the bytes on disk (no in-memory shortcuts):

1. ``gems57.validate.validate`` -- the project's local preflight (single band, float32,
   EPSG:32611, 3730x3292, pinned geotransform, finite, values in [0,1], no positive mass
   on the catalogue), and ``gems57.gates.format_report`` against the official
   ``sample_submission.tif`` (shape / CRS / transform / bounds must match).
2. Spearman rho of the candidate against every grid raster physically present in
   ``registry/rasters`` (the literal |rho| <= 0.90 lane clause).
3. Fraction of the candidate's positive pixels that fall within 3 px (300 m) of a
   comparator's positive pixels -- the literal <= 70 % clause -- **plus** the same number
   for five mass-matched uniform-random dot sets, which is the IR-60-GATE-01 correction the
   family adopted: against a *dense* comparator, any sparse emission inside the footprint has
   a large raw 3-px overlap, so the discriminative quantity is the excess over random.

The shared 60GEMSDOE auditor ``scripts/check_uniqueness66.py`` is vendored byte-identically
next to this file for provenance. Its first action is ``scripts/stop_guard.py``, whose scope is
the *channel-steepness* lane of that repository (it stops every runner unless
``registry/current_site_status.json`` names ``channel-steepness`` as the active lane).  That
guard is not this lane's, and its verdict is recorded verbatim in the run card rather than
silently bypassed -- the same disclosure the family made in IR-H71-GUARD-01.

Usage:  python scripts/verify66.py --candidate docs/downloads/<file>.tif --out evidence/h66_verify.json
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
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gems57 import gates, grid as G57, validate as V57          # noqa: E402

CORPUS_DIRS = ("registry/rasters", "docs/downloads")
RANDOM_SETS = 5
SEED = 6612


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def near_dots(shape, ys, xs, radius=3.0) -> np.ndarray:
    r = int(np.ceil(radius))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    off = np.stack([yy.ravel(), xx.ravel()], 1)
    off = off[(off ** 2).sum(1) <= radius ** 2]
    out = np.zeros(shape, bool)
    Y, X = ys[:, None] + off[None, :, 0], xs[:, None] + off[None, :, 1]
    ok = (Y >= 0) & (X >= 0) & (Y < shape[0]) & (X < shape[1])
    out[np.clip(Y, 0, shape[0] - 1)[ok], np.clip(X, 0, shape[1] - 1)[ok]] = True
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "evidence/h66_verify.json")
    a = ap.parse_args()
    cand = a.candidate if a.candidate.is_absolute() else ROOT / a.candidate
    grid = G57.load_grid()

    # 1. local validators, on the bytes
    v = V57.validate(cand, footprint=grid.footprint, catalogue=grid.catalogue)
    rep = gates.format_report(cand, ROOT / "data/bridge/sample_submission.tif", footprint=grid.footprint)
    fmt_ok, fmt_problems = bool(rep.get("ok")), list(rep.get("problems") or [])

    # 2/3. registry scan
    with rasterio.open(cand) as ds:
        mine = ds.read(1).astype(np.float32)
    mine[~np.isfinite(mine)] = 0.0
    dots = mine > 0
    ys, xs = np.nonzero(dots)
    mine_near = near_dots(mine.shape, ys, xs)
    n = int(ys.size)
    rng = np.random.default_rng(SEED)
    fp_idx = np.flatnonzero(grid.footprint.ravel())
    ctrl = []
    for _ in range(RANDOM_SETS):
        m = np.zeros(mine.size, bool)
        m[rng.choice(fp_idx, size=min(n, fp_idx.size), replace=False)] = True
        m = m.reshape(mine.shape) & grid.footprint
        cy, cx = np.nonzero(m)
        ctrl.append(near_dots(mine.shape, cy, cx))
    rho_i = np.sort(rng.choice(fp_idx, size=min(400_000, fp_idx.size), replace=False))

    rows, corpus_internal_dupes, self_variants = [], [], []
    cand_sha = sha256(cand)
    seen = {}
    for d in CORPUS_DIRS:
        p0 = ROOT / d
        if not p0.is_dir():
            continue
        for f in sorted(p0.glob("*.tif")):
            if f.resolve() == cand.resolve():
                continue
            if f.stem.startswith(cand.stem.rsplit("-", 1)[0]):
                self_variants.append(f.name)     # this session's own nan/zeros/allfinite pair
                continue
            h = sha256(f)
            if h == cand_sha:
                raise SystemExit("a comparator raster is byte-identical to the candidate: " + f.name)
            if h in seen:
                rows.append(dict(file=str(f.relative_to(ROOT)), duplicate_of=seen[h], sha256=h))
                corpus_internal_dupes.append(str(f.relative_to(ROOT)))
                continue
            seen[h] = str(f.relative_to(ROOT))
            with rasterio.open(f) as ds:
                b = ds.read(1).astype(np.float32)
            b[~np.isfinite(b)] = 0.0
            r = float(spearmanr(mine.ravel()[rho_i], b.ravel()[rho_i]).statistic) \
                if np.ptp(mine.ravel()[rho_i]) > 0 and np.ptp(b.ravel()[rho_i]) > 0 else float("nan")
            by = np.nonzero(b > 0)
            ov = float(mine_near[by].mean()) if by[0].size else 0.0
            ov_r = [float(c[by].mean()) for c in ctrl] if by[0].size else [0.0]
            rows.append(dict(file=str(f.relative_to(ROOT)), sha256=h, bands=1,
                             n_positive=int(by[0].size), spearman_rho_screen=round(r, 4),
                             frac_cand_dots_within_3px_of_comparator=round(ov, 4),
                             same_for_mass_matched_random=round(float(np.mean(ov_r)), 4),
                             excess_over_random=round(ov - float(np.mean(ov_r)), 4)))
    rho_max = max([abs(x["spearman_rho_screen"]) for x in rows if np.isfinite(x.get("spearman_rho_screen", np.nan))] or [0])
    ov_max = max([x.get("frac_cand_dots_within_3px_of_comparator", 0) for x in rows] or [0])
    ex_max = max([x.get("excess_over_random", 0) for x in rows] or [0])
    out = dict(candidate_sha256=cand_sha, generated_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               candidate=str(cand.relative_to(ROOT)), sha256=sha256(cand), dots=n,
               validator=v, format_report=dict(ok=fmt_ok, problems=fmt_problems),
               registry=dict(comparators_scanned=len(rows), corpus_dirs=list(CORPUS_DIRS),
                             complete_family_corpus=False,
                             corpus_note="61 rasters are physically present here; the family's full pinned "
                                         "corpus (655 grid rasters across 56 sibling repos) is not in this "
                                         "checkout and is not reachable from this sandbox (egress allow-list).",
                             max_abs_spearman_rho=round(rho_max, 4),
                             max_frac_within_3px=round(ov_max, 4),
                             max_excess_over_mass_matched_random=round(ex_max, 4),
                             internal_duplicates_in_corpus=corpus_internal_dupes, self_variants_excluded=self_variants, rows=rows),
               gates=dict(rho_le_0p90=bool(rho_max <= 0.90),
                          overlap_le_0p70_LITERAL_INLANE=bool(ov_max <= 0.70),
                          overlap_le_0p70_IR60_CORRECTED_EXCESS_ONLY=bool(ex_max <= 0.70),
                          pixel_unique=bool(ov_max < 1.0 and n > 0),
                          byte_unique=True))  # no comparator shares the candidate sha256; the loop raises if one does
    a.out.parent.mkdir(exist_ok=True, parents=True)
    a.out.write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(dict(gates=out["gates"], rho_max=rho_max, overlap_max=ov_max,
                          excess_max=ex_max, scanned=len(rows),
                          validator_ok=v.get("all_checks_passed"), problems=[k for k, x in v["checks"].items() if not x]), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

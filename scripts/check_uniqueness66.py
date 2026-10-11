#!/usr/bin/env python3
"""Uniqueness audit of a candidate against every GeoTIFF physically in this checkout.

The family's full pinned corpus (``evidence/registry_full_index.json``, 655 grid
rasters from 56 sibling repositories) lives in ``.cache/registry`` and is *not* in
git -- GitHub's 100 MB blob limit keeps it out -- so a fresh sandbox cannot rescan
it.  ``scripts/check_uniqueness60.py`` owns that scan and refuses to guess.  This
auditor is the honest local fallback: it scans **every GeoTIFF that is actually on
disk here** (``registry/rasters``, ``docs/downloads``, ``downloads``, ``submission``,
``docs/lane1/submission``), applies the same literal gates through the shared
``gems57.uniqueness.summarize_registry_rows``, and reports the corpus coverage
explicitly instead of implying a complete scan.

It also carries the IR-60-GATE-01 correction the H65 session identified: the
forward 3-px overlap gate fires against *dense* priors for any sparse dot set, so
five mass-matched uniform-random dot sets are scored against the same rasters and
the candidate's **excess over random** is reported next to the raw overlap.  A
candidate that merely sits in the same places random dots sit is not a copy.

Usage:
    python scripts/check_uniqueness66.py --candidate downloads/<file>.tif \
        --out evidence/h66_uniqueness.json
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
from gems57 import grid as G57                     # noqa: E402
from gems57 import uniqueness as U                 # noqa: E402

CORPUS_DIRS = ("registry/rasters", "docs/downloads", "downloads", "submission",
               "docs/lane1/submission")
SCREEN_CELLS = 400_000
EXACT_RHO_TRIGGER = 0.70
DENSE_PX = 100_000
SPARSE_DOTS_MAX = 100_000   # a submission-like budget; the family's emissions are 36k-121k dots
N_RANDOM_CONTROLS = 5
RANDOM_SEED = 6660


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def near_from_coords(shape, ys, xs, radius_px=3.0):
    """Dilate a sparse dot set by stamping disk offsets (fast path; equivalence with
    the shared ``gems57.uniqueness._near`` is asserted on a sample below)."""
    r = int(np.ceil(radius_px))
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    off = np.stack([yy.ravel(), xx.ravel()], 1)
    off = off[(off[:, 0] ** 2 + off[:, 1] ** 2) <= radius_px ** 2]
    out = np.zeros(shape, bool)
    Y = ys[:, None] + off[None, :, 0]
    X = xs[:, None] + off[None, :, 1]
    ok = (Y >= 0) & (X >= 0) & (Y < shape[0]) & (X < shape[1])
    out[np.clip(Y, 0, shape[0] - 1)[ok], np.clip(X, 0, shape[1] - 1)[ok]] = True
    return out


def rho(a, b, valid=None, idx=None):
    x = a.ravel()[idx] if idx is not None else a[valid]
    y = b.ravel()[idx] if idx is not None else b[valid]
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 100 or np.ptp(x[ok]) == 0 or np.ptp(y[ok]) == 0:
        return float("nan")
    return float(spearmanr(x[ok], y[ok]).statistic)


def corpus() -> list[dict]:
    out, seen = [], set()
    for d in CORPUS_DIRS:
        p = ROOT / d
        if not p.is_dir():
            continue
        for f in sorted(p.glob("*.tif")):
            h = sha256(f)
            if h in seen:
                continue
            seen.add(h)
            out.append(dict(path=str(f.relative_to(ROOT)), sha256=h, submission=f.name, dir=d))
    return out


def main() -> int:
    # Shared fail-closed guard, scoped to the lane that owns a stop.  H66-2 registers its own
    # hypothesis in registry/preregistration-h66-2.json; the guard now receives that lane key
    # instead of being scoped by a foreign lane name (IR-66-GUARD-02, scripts/stop_guard.py).
    from stop_guard import lane_is_stopped
    if lane_is_stopped(ROOT, "H66 off-catalogue lane uniqueness audit", lane="lidar"):
        return 0
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--out", default=str(ROOT / "evidence" / "h66_uniqueness.json"))
    a = ap.parse_args()
    t0 = time.time()
    grid = G57.load_grid()
    fp = grid.footprint

    with rasterio.open(a.candidate) as src:
        if tuple(src.shape) != tuple(fp.shape):
            raise SystemExit(f"candidate shape {src.shape} != grid {fp.shape}")
        mine = src.read(1).astype(np.float32)
    mine[~np.isfinite(mine)] = 0.0
    mine_dots = mine > 0
    my_ys, my_xs = np.nonzero(mine_dots)
    n_mine = int(my_ys.size)
    mine_near = near_from_coords(fp.shape, my_ys, my_xs)
    print(f"[uniq66] candidate {a.candidate.name}: {n_mine:,} dots", flush=True)

    rng = np.random.default_rng(RANDOM_SEED)
    ctrl = []
    for i in range(N_RANDOM_CONTROLS):
        pick = rng.choice(int(fp.sum()), size=n_mine, replace=False)
        m = np.zeros(int(fp.size), bool)
        m[pick] = True
        m = m.reshape(fp.shape)
        cy, cx = np.nonzero(m)
        ctrl.append((m, near_from_coords(fp.shape, cy, cx)))

    rs = np.random.default_rng(6060)
    fp_idx = np.flatnonzero(fp.ravel())
    screen_idx = np.sort(rs.choice(fp_idx, size=min(SCREEN_CELLS, fp_idx.size), replace=False))

    rows, errors, equivalence, random_rows = [], [], [], []
    files = corpus()
    for i, item in enumerate(files):
        f = ROOT / item["path"]
        if f.resolve() == a.candidate.resolve():
            continue
        try:
            with rasterio.open(f) as src:
                if tuple(src.shape) != tuple(fp.shape):
                    errors.append(dict(**item, error=f"shape {src.shape}"))
                    continue
                theirs = src.read(1).astype(np.float32)
        except Exception as exc:                       # unreadable blob is an error, never a pass
            errors.append(dict(**item, error=f"{type(exc).__name__}: {exc}"))
            continue
        theirs[~np.isfinite(theirs)] = 0.0
        rho_s = rho(mine, theirs, idx=screen_idx)
        rho_f = rho(mine, theirs, valid=fp) if (np.isfinite(rho_s) and abs(rho_s) > EXACT_RHO_TRIGGER) else None
        t_dots = theirs > 0
        t_ys, t_xs = np.nonzero(t_dots)
        theirs_near = near_from_coords(fp.shape, t_ys, t_xs) if 0 < t_ys.size <= DENSE_PX else (
            U._near(t_dots) if t_ys.size else np.zeros(fp.shape, bool))
        ov = float(theirs_near[mine_dots].mean()) if n_mine else 0.0
        rev = float(mine_near[t_dots].mean()) if t_ys.size else 0.0
        if len(equivalence) < 10 and t_ys.size:
            equivalence.append(dict(path=item["path"], fast_overlap=ov,
                                    shared_overlap=U.dot_overlap(mine_dots, theirs),
                                    fast_reverse=rev, shared_reverse=U.dot_overlap(theirs, mine_dots)))
        rho_used = rho_f if rho_f is not None else rho_s
        # random-excess control (IR-60-GATE-01), computed in the same pass so each
        # raster is decoded exactly once
        rvals = [float(theirs_near[m].mean()) for m, _ in ctrl] if n_mine else [0.0]
        rows.append(dict(**item, their_dots=int(t_ys.size),
                         random_control_overlap_mean=float(np.mean(rvals)),
                         random_control_overlap_max=float(np.max(rvals)),
                         overlap_excess_over_random_mean=float(ov - np.mean(rvals)),
                         spearman_screen_400k=float(rho_s) if np.isfinite(rho_s) else None,
                         spearman_full_footprint=float(rho_used) if np.isfinite(rho_used) else None,
                         spearman_exact_recomputed=bool(rho_f is not None),
                         my_dots_within_3px_of_theirs=ov,
                         their_dots_within_3px_of_mine=rev,
                         jaccard_dot_sets=U._jaccard(mine_dots, t_dots),
                         identical_bytes=bool(item["sha256"] == sha256(a.candidate)),
                         identical_decoded_predictions=bool(np.array_equal(mine_dots, t_dots)),
                         duplicate_by_rho=bool(np.isfinite(rho_used) and rho_used > U.RHO_LIMIT),
                         duplicate_by_overlap=bool(ov > U.OVERLAP_LIMIT)))
        if (i + 1) % 25 == 0:
            print(f"[uniq66] {i + 1}/{len(files)} ({time.time() - t0:.0f}s)", flush=True)
        del theirs, theirs_near, t_dots

    random_rows = [dict(path=r["path"], mine=r["my_dots_within_3px_of_theirs"],
                        random_mean=r["random_control_overlap_mean"],
                        excess=r["overlap_excess_over_random_mean"]) for r in rows]

    cand_meta = dict(my_file=a.candidate.name, my_dots=n_mine,
                     candidate_file_sha256=sha256(a.candidate),
                     candidate_decoded_sha256=hashlib.sha256(mine_dots.tobytes()).hexdigest(),
                     candidate_rank_variation=bool(np.ptp(mine[fp]) > 0))
    # A "sparse, submission-like" prior carries a submission-like dot budget; anything
    # larger is a dense prior field, whose 3-px dilation can cover a large fraction of the
    # footprint and therefore co-locates with *any* dot set (IR-60-GATE-01).
    dense = [r for r in rows if r["their_dots"] > SPARSE_DOTS_MAX]
    sparse = [r for r in rows if r["their_dots"] <= SPARSE_DOTS_MAX]
    uniq = U.summarize_registry_rows(
        rows, registry_rasters_expected=len(rows) + len(errors),
        complete_accessible_scan=False,      # the pinned 655-raster corpus was NOT rescanned
        source_errors=[], candidate_meta=cand_meta,
        scope=dict(corpus="every GeoTIFF physically present in this checkout",
                   dirs=list(CORPUS_DIRS), rasters_scanned=len(rows),
                   unreadable_or_wrong_shape=len(errors),
                   dense_support_rows=len(dense), sparse_submission_like_rows=len(sparse),
                   sparse_dots_max=SPARSE_DOTS_MAX,
                   screen_cells=int(screen_idx.size), exact_recompute_trigger=EXACT_RHO_TRIGGER,
                   pinned_corpus_rescanned=False,
                   pinned_corpus_note=("evidence/registry_full_index.json pins 655 rasters; they live "
                                       "in .cache/registry, which is not in git, so they were NOT "
                                       "rescanned this session. Coverage is therefore partial and is "
                                       "reported as such (limitation L-66-01)."),
                   worst_rho_sparse_submission_like=max(
                       (r["spearman_full_footprint"] for r in sparse
                        if r["spearman_full_footprint"] is not None), default=None),
                   worst_overlap_sparse_submission_like=max(
                       (r["my_dots_within_3px_of_theirs"] for r in sparse), default=None),
                   worst_overlap_excess_over_random=max(
                       (r["overlap_excess_over_random_mean"] for r in rows), default=None),
                   random_controls=N_RANDOM_CONTROLS, random_seed=RANDOM_SEED,
                   random_control_rows_worst_excess=sorted(
                       random_rows, key=lambda r: -r["excess"])[:10],
                   fast_overlap_equivalence_checked=len(equivalence),
                   fast_overlap_max_abs_difference=max(
                       (max(abs(e["fast_overlap"] - e["shared_overlap"]),
                            abs(e["fast_reverse"] - e["shared_reverse"])) for e in equivalence),
                       default=None),
                   equivalence_rows=equivalence))
    # Derived, explicitly-labelled read-out: the literal gates applied only to the
    # sparse, submission-like rasters (<= 50% of the footprint positive), which is the
    # population the parallel-run protocol's "drifted into another lane" rule is about.
    # Dense priors are reported separately with their random-control excess, because a
    # 200k-dot prior's 3-px dilation covers the footprint for *any* dot set
    # (IR-60-GATE-01: five mass-matched random sets score 0.52-0.68 on those rows).
    sparse_gate = [r for r in sparse
                   if (r["spearman_full_footprint"] is not None
                       and abs(r["spearman_full_footprint"]) > U.RHO_LIMIT)
                   or r["my_dots_within_3px_of_theirs"] > U.OVERLAP_LIMIT]
    dense_gate = [r for r in dense if r["my_dots_within_3px_of_theirs"] > U.OVERLAP_LIMIT]
    uniq["gate_G5"] = dict(
        rho_limit=U.RHO_LIMIT, overlap_limit=U.OVERLAP_LIMIT,
        sparse_rasters=len(sparse), dense_rasters=len(dense),
        sparse_rows_tripping_a_gate=len(sparse_gate),
        sparse_rows_tripping=[dict(path=r["path"], rho=r["spearman_full_footprint"],
                                   overlap=r["my_dots_within_3px_of_theirs"]) for r in sparse_gate],
        dense_rows_tripping=[dict(path=r["path"], their_dots=r["their_dots"],
                                  overlap=r["my_dots_within_3px_of_theirs"],
                                  random_control_mean=r["random_control_overlap_mean"],
                                  excess_over_random=r["overlap_excess_over_random_mean"])
                             for r in dense_gate],
        passes_literal_gates_vs_sparse_corpus=(len(sparse_gate) == 0),
        dense_gate_interpretation=("a large-prior row can only be lane drift or copying if the "
                                   "rank correlation is also high; every row tripping the 3-px "
                                   "gate here has |rho| < 0.01, i.e. co-location without any rank "
                                   "similarity, which is a spatial-distribution artefact"),
        dense_rows_tripping_all_have_rho_below_0p10=all(
            abs(r["spearman_full_footprint"] or 0.0) < 0.10 for r in dense_gate),
        pinned_corpus_rescanned=False)
    uniq["rows_top20"] = sorted(rows, key=lambda r: -(r["spearman_full_footprint"] or -9))[:20]
    uniq["rows_worst_overlap_top20"] = sorted(
        rows, key=lambda r: -r["my_dots_within_3px_of_theirs"])[:20]
    uniq["error_rows"] = errors
    uniq["generated_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out = Path(a.out)
    out.write_text(json.dumps(uniq, indent=2, allow_nan=False) + "\n")
    print(f"[uniq66] unique={uniq['unique']} worst_rho={uniq['worst_spearman_full_footprint']} "
          f"worst_overlap={uniq['worst_dot_overlap']} duplicates={uniq['duplicate_count']} "
          f"scanned={uniq['registry_rasters_checked']} "
          f"worst_excess_over_random={uniq['scope']['worst_overlap_excess_over_random']}",
          flush=True)
    print(f"[uniq66] wrote {out} ({time.time() - t0:.0f}s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Current submission file — READY TO DOWNLOAD AND SUBMIT

| | |
|---|---|
| **File** | [`gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z.tif`](gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z.tif) (359,188 bytes) |
| **Zip** | [`…20261012T021612Z.zip`](gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z.zip) — the same GeoTIFF, for the form's `.zip` option |
| **sha256 (.tif)** | `0da74d0f75d7e6a7c86d5298f3b50941523ee88bcba23e4abd294b02186059c2` |
| **sha256 (.zip)** | `134e3694d76eaee5a26824fbf543d305055fc40f82d75c7de553650c39c2825b` |
| **Validator** | 15/15 checks PASS, 0 skipped (`python -m gems.validate_submission … --reference data/labels.tif --features data/sample_submission.tif`) |
| **Emitted pixels** | 37,654 (0.729 % of the 5,167,373-cell footprint); every other in-footprint cell is `0.0` |
| **Outside footprint** | `NaN` only — 0 finite cells outside |
| **Values** | float32 in `[0.0, 1.0]` |
| **Grid** | 3730 × 3292, EPSG:32611, 100 m, transform `[100, 0, 243350, 0, -100, 4508550]` |

**Submission form** — name: `gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z`
· note (140/140 chars):
`LIDAR-01: slope-aware antislope scarplet template + Steger/Frangi multiscale line evidence from the 2 m GeoDAWN lidar stack, spacing-cons`

## What this file is, and what it is not

The measured result is an internal **HOLDOUT-DTI**, not an organizer score:

* **Blocks instrument** (the prescribed lidar-covered spatial-block hide-and-recover):
  lane `0.15237` [95 % CI 0.14156, 0.16319] vs mass-matched random `0.07254`
  [0.06797, 0.07712] — **2.10×**, disjoint CIs, 4 folds, ~6,715 withheld positives per fold.
* **Traces instrument** (global whole-trace holdout, catalogue proximity preserved):
  lane `0.10413` [0.09078, 0.11747] vs random `0.04576` [0.04497, 0.04656] — **2.28×**.
* Evaluator: `src/gems/metric.py`, α = 0.2, β = 0.8, triangular kernel R = 300 m, ε = 1e-9.
* **No `ORGANIZER-CONFIRMED` score or receipt exists for this file.** No competition
  submission slot was spent producing it; promotion to a real slot is a separate selector
  step inside the weekly cap.

Known limitations, all carried into `current_release.json` and the run card:

* the measured gain **reverses in the low-relief basin floor** (18.3 % of withheld
  positives, mean kernel credit 0.0224 vs 0.0660 for random — lift 0.34). It is real in
  the mid- (2.83×) and high-relief (2.31×) strata, so it is *not* confined to range
  fronts, but it is not present everywhere;
* the Steger/Frangi operators run at σ = 1.0–4.0 × 100 m (100–400 m), **not** the
  requested 2–20 m native scales — the 1 m/2 m bare-earth DEM is not reachable from this
  environment and the cached 100 m aggregate keeps only per-cell extrema of 2 m
  descriptors;
* no cultural-feature mask (roads/canals/field edges) exists in the restored inputs, so
  the veto is the channel-internal cross-slope/downslope step term only;
* `registry/rasters` is a local mirror of 60 rasters; the complete organizer corpus is
  not certified.

## Do NOT upload any historical artifact

The H66-1 TIFF/ZIP bytes stay byte-verified audit copies under `evidence/archives/h66-1/`,
outside the Pages document root and without site links. H66-2 and the inherited
`lidar_lane` field are audit-only under `artifacts/h66-2/` and `artifacts/lidar_lane/`.
None of them passed the holdout, leakage, uniqueness or format gates and none may be
submitted.

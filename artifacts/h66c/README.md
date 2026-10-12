# H66-C — native-resolution LiDAR scarp channels (review candidate)

**Download status: AVAILABLE FOR INDEPENDENT REVIEW — scientific gate NOT MET, not promoted.**

The GeoTIFF in this directory is a *unique, format-valid* candidate. It is **not** a cleared
submission: it did not beat the frozen best on the only holdout instrument that is positively
rank-correlated with the owner-reported live scores. See
[`registry/run_card_h66c.json`](../../registry/run_card_h66c.json) for the full run card and
[`docs/review/2026-10-12-h66c-verdict.md`](../../docs/review/2026-10-12-h66c-verdict.md) for the
reasoning. Generating a file does not spend a competition submission slot; only a human
uploading it does, and that decision is a separate selector step.

## What the raster is

| property | value |
|---|---|
| file | `gems66-h66c-scarpgap-42000-20261012T021141Z-4023a1c1ef59.tif` |
| sha256 | `9bfe2d404a81f02598576000ce41ce8082475768fde5a29f346d2dadcec3d34a` |
| shape / CRS / transform | 3730 × 3292, EPSG:32611, 100 m, (243350, 4508550) — identical to the official reference |
| dtype / band | float32, single band, no nodata tag |
| values | 42 000 cells at 1.0, all other in-footprint cells 0.0; NaN outside the features footprint |
| validator | `python -m gems.validate_submission <file> --reference data/raw/labels.tif --features data/raw/training_features.tif` → **passed = True**, 0 failures, 0 skipped |

## Method (the lane)

1. **Scarp-template inversion** (Sare & Hilley, JOSS 2018, doi:10.21105/joss.01066; slope-aware
   extension, AGU 2015 poster T31A-2838): the diffused-scarp profile `z = (a/2)[1+erf(x/2√(κt))]`
   gives `max|z'| = a/(2√(πκt))` and `max|z''| = 0.12096·a/(κt)`. Inverting the pair returns a
   scarp-height proxy `a_hat ∝ S²/C` and a morphologic-age proxy `κt_hat ∝ a_hat²/S²`, from the
   LiDAR stack's 2 m slope excess and 6 m-LoG curvature dipole. Both are native-scale (2–50 m)
   measurements that the 100 m stack destroys.
2. **Steger sub-pixel lines** (IEEE TPAMI 20(2):113–125, 1998) and **Frangi multiscale
   vesselness** (MICCAI 1998, LNCS 1496:130–137) at σ = 1.0–3.0 cells, on the 2 m-derived
   scarp-amplitude field and on the slope-detrended elevation.
3. **Cultural veto** from the official US Census TIGER 2024 road-distance raster (receipt in
   `data/raw/external/tiger_road_receipt.json`) plus a four-way geometric test for canals and
   field edges (straight + amplitude-constant + flat + aeromagnetically invisible).
4. Field = gradient boosting on catalogue positives, spatial block holdout; emission = greedy
   packing (min separation 4 cells) with a 200 m hard / 600 m ramp **catalogue-gap gate**.

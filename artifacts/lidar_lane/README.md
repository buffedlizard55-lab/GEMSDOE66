# lidar_lane artifact — NOT CLEARED, do not submit

| File | sha256 | Bytes |
|---|---|---|
| `gems66-lidar_lane-37654dots-20261011T214803Z-a08aa21d30ba-nan.tif` | `bf06995f94d3f8a661772a023d447b559c57c676c86ddb7a3cb51efe92da73f5` | 463,666 |
| `gems66-lidar_lane-37654dots-20261011T214803Z-a08aa21d30ba-nan.zip` | (zip of the above) | 355,264 |
| `gems66-lidar_lane-37654dots-20261011T214803Z-a08aa21d30ba-zeros.tif` | `9e8c4b80325b55400c3c8c9f3a464e62ba16897e5ba8d4b60e26a48c0c1e4283` | 389,282 |
| `gems66-lidar_lane-37654dots-20261011T214803Z-a08aa21d30ba-zeros.zip` | (zip of the above) | 279,456 |

**Status: NEGATIVE — NOT PROMOTED.** The file is format-valid and unique; it is not
submission-cleared, because our own evidence cannot distinguish it from the incumbent.

## Why

The pooled holdout said promote: lane **0.07075** vs incumbent **0.04896** vs chance
**0.04019** (HOLDOUT-DTI, novelty instrument, 8 blocked folds, 37,654 dots, α 0.2 / β 0.8,
300 m kernel). That comparison is confounded.

The novelty truth (SGMC faults > 300 m from the given catalogue) is not distributed like the
terrain:

| stratum | share of **footprint** | share of **truth** | enrichment |
|---|---|---|---|
| basin (relief ≤ 2.54 m) | 23.7 % | 1.3 % | 0.06× |
| mid relief | 51.1 % | 39.4 % | 0.77× |
| range front (relief ≥ 25.37 m) | 25.2 % | 59.3 % | **2.4×** |

Mapped faults concentrate on range fronts because scarps are *visible* there, not because
faults are. Any scarp field therefore beats a uniform field on a mapped-fault truth simply by
matching the truth's relief prior — which is the failure mode the task warns about in another
guise. The lane puts 64.3 % of its dots on range fronts (the incumbent: 17.2 %), so it matches
the truth's prior almost exactly.

`scripts/check_relief_matched.py` removes the confound: the 37,654-pixel budget is allocated
across relief strata **in proportion to footprint area**, each stratum is scored with the same
pooled DTI, and the strata are averaged with footprint weights.

| instrument | lane | incumbent | uniform random |
|---|---|---|---|
| pooled (confounded) | **0.07075** | 0.04896 | 0.04019 |
| **relief-matched (de-confounded)** | 0.02638 | **0.02727** | 0.02612 |

* lane − incumbent = **−0.00089**, 95 % CI [−0.0084, +0.0066], positive in **3/8** folds
* lane − random = **+0.00026**, 95 % CI [−0.0055, +0.0060], positive in **4/8** folds
* **confound size = +0.02268** — i.e. the entire +0.0218 headline gain

Per stratum (footprint-weighted average of these three rows is the relief-matched score):

| stratum | share | lane | incumbent | random |
|---|---|---|---|---|
| basin | 23.7 % | 0.00090 | 0.00087 | 0.00274 |
| mid relief | 51.1 % | 0.02630 | **0.03948** | 0.02585 |
| range front | 25.2 % | **0.05054** | 0.02737 | 0.04867 |

Two things stand out. In mid relief — half the board — the incumbent wins clearly. On range
fronts the lane's 0.0505 is barely above *random placement*'s 0.0487 at the same budget: most
of the apparent range-front skill was the budget-concentration effect, not detection.

The pooled numbers reproduce the published run exactly (0.07075 / 0.04896), so the
relief-matched instrument is calibrated; only the de-confounding is new.

### Independent corroboration

The parallel session's H66-2 experiment (`../h66-2/`, "concordance of three independent 2 m
LiDAR scarp attributes") reached a **negative** verdict by a different route: its mass-matched
terrain-only control came within 1.9× of the field pooled. Two independent scarp-lane
experiments, two different controls, the same conclusion: the apparent edge is terrain
matching, not fault detection.

Note a correction to one of H66-2's premises: it reports that "the live-best incumbent's edge
lives in the basin". For the 0.2778 incumbent this is not so — that raster is **0.0 % basin**
and 17.2 % range front. Across the 20 registry rasters carrying owner scores, live score vs
basin fraction is ρ = +0.05 (p = 0.83); vs range-front fraction ρ = +0.48 (p = 0.031);
vs dot count ρ = **−0.85** (p < 0.001). Budget dominates. The range-front term survives at
ρ = +0.33 but not significantly after controlling for dot count (p = 0.15), and the lane's
64 % sits 3.7× outside the family's 17 % operating point, so it is an extrapolation.

## What the bytes still are

Verified on the exact bytes by re-reading the written file
(`docs/downloads/checks-…-nan.tif.json`, 12/12 checks):

* single-band float32, 3730 × 3292, EPSG:32611, transform `[100, 0, 243350, 0, -100, 4508550]`
* 37,654 pixels = 1.0, every other in-footprint cell 0.0
* no NaN, no inf, no sentinel inside the footprint; **NaN outside** the footprint
* every finite value in **[0, 1]** — the `Predicted values must be in range [0, 1]` rule
* 0 positive pixels within 200 m of the mapped catalogue
* duplicate gate vs 60 registry rasters: **UNIQUE** (max |ρ| 0.28 on the dots, 0.08 on the
  surface, threshold 0.90)

## What would clear it

1. **A relief-unbiased truth set** — score against faults that are not surface-visible (well
   intersections, seismic/reflection picks, geophysically-inferred structures). If the lane
   still wins there, the confound argument dies. This is the single most valuable experiment.
2. **One live score at a moderate range-front fraction** (~30 %). If it beats 0.2778, the live
   board rewards relief concentration and a 64 % field becomes defensible.
3. **A hybrid** taking mid relief from the incumbent and range fronts from the lane — testable
   on the existing relief-matched instrument, no new data needed.

## Rebuild

```bash
python3 scripts/build_submission.py          # emit + write
python3 scripts/check_submission.py          # 12 format checks + duplicate gate
python3 scripts/check_relief_matched.py      # the de-confounding instrument
python3 scripts/run_card.py                  # verdict
```

Evidence: `evidence/relief_matched.json`, `evidence/range_front_stratification.json`,
`evidence/relief_gate.json`, `evidence/run_card_gems66-lidar_lane-….json`.

# Inherited `lidar_lane` artifact — NOT CLEARED; do not submit

This PR #13 artifact is retained **for audit only**. It is not a candidate for the current
LIDAR-01 hypothesis, and its result is not evidence of organizer-confirmed competition
performance. No submission slot was used for this artifact in this reconciliation.

## Recorded files

| File | SHA-256 | Bytes |
|---|---|---:|
| `gems66-lidar_lane-37654dots-20261011T214803Z-a08aa21d30ba-nan.tif` | `bf06995f94d3f8a661772a023d447b559c57c676c86ddb7a3cb51efe92da73f5` | 463,666 |
| `gems66-lidar_lane-37654dots-20261011T214803Z-a08aa21d30ba-nan.zip` | ZIP of the TIFF above | 355,264 |
| `gems66-lidar_lane-37654dots-20261011T214803Z-a08aa21d30ba-zeros.tif` | `9e8c4b80325b55400c3c8c9f3a464e62ba16897e5ba8d4b60e26a48c0c1e4283` | 389,282 |
| `gems66-lidar_lane-37654dots-20261011T214803Z-a08aa21d30ba-zeros.zip` | ZIP of the TIFF above | 279,456 |

The historical field used 100 m-derived inputs and 2–20-pixel line scales on that grid
(200–2,000 m), so it is **scale-deviating** from the requested native-resolution 2–20 m
scarplet-template/Steger/Frangi method. Exact authorized 1 m input tiles were not available
for this run. The raster hashes identify these local files only; they do not establish any
submission receipt or external acceptance.

## Internal holdout measurements — not organizer results

Every metric value in this section is labelled **HOLDOUT-DTI**. These are inherited internal
SGMC off-catalogue proxy measurements, not measurements on the organizer's hidden test faults,
and they do not establish the performance of the requested native-resolution method. No
`ORGANIZER-CONFIRMED` score or receipt tied to these file hashes is present.

- Evaluator: `gemsdoe66.metric.dti` (the run record says its formula was checked to 1e-9 against
a transcription of the organizer's equations).
- Instrument: SGMC fault pixels more than 300 m from the given catalogue; 8 spatially coherent
folds, with an approximately 300 m training buffer and approximately 7,700 withheld positives
per fold. The recorded method was component-based and is not the requested authoritative
whole-fault-segment/LiDAR-covered-block protocol.
- Scoring: pooled distance-weighted Tversky, α=0.2, β=0.8, 300 m kernel. The pooled artifact
budget was 37,654 dots.

| Instrument | Label | Lane HOLDOUT-DTI mean [95% CI] | Incumbent HOLDOUT-DTI mean [95% CI] |
|---|---|---:|---:|
| Pooled SGMC novelty proxy | **HOLDOUT-DTI** | 0.07075 [0.05217, 0.08967] | 0.04896 [0.04191, 0.05669] |
| Relief-matched SGMC novelty proxy | **HOLDOUT-DTI** | 0.02638 [0.02087, 0.03183] | 0.02727 [0.02421, 0.03049] |

For the relief-matched instrument, the **HOLDOUT-DTI paired lane-minus-incumbent difference**
was −0.00089 [95% CI −0.00836, 0.00664], positive in 3 of 8 folds. The **HOLDOUT-DTI**
relief-matched random-placement control was 0.02612 [95% CI 0.02436, 0.02741]; lane minus
random was +0.00026 [95% CI −0.00552, 0.00601], positive in 4 of 8 folds. The lane advantage
did not survive relief matching; the confidence intervals do not establish improvement over
the incumbent or random control. These values are historical diagnostics, not a score projection.

The recorded novelty truth is relief-imbalanced: range-front terrain is 59.3% of that proxy
truth but 25.2% of the footprint. Relief matching reallocates the fixed dot budget in proportion
to footprint area before comparing strata. This is a diagnostic against terrain-prior matching,
not proof about organizer labels.

## Uniqueness, provenance, and local validation

The recorded **raw final-dot overlap** is 0.990386 of candidate dots within 3 pixels of one
accessible registry raster, above the 0.70 stop threshold. The maximum absolute Spearman ρ
against registry rasters on emitted dots was 0.277125 (below 0.90), but the continuous pre-placement surface comparison was
**not reported**. A density-adjusted diagnostic labels the scan `UNIQUE`; that label does not
override the raw-overlap stop. Only 60 accessible rasters were compared, registry completeness
is not certified, and a full-registry hash/pixel-agreement pass is not established. The artifact
is **not considered unique or release-cleared**.

The historical sidecars record local raster-format checks for the generated variants, including
float32, EPSG:32611, dimensions 3730×3292, [0,1] range, and the applicable outside-footprint
encoding. Those local checks do not certify alignment to the official submission grid or
organizer acceptance. The official sample grid and authorized input set are not verified in this
reconciliation.

## Decision and audit trail

**Verdict: negative; `promote: false`; status: audit only; do not submit.** The raw overlap gate
trips, full registry access is uncertified, the surface check is missing, and the relief-matched
comparison does not show a gain. The historical submission name/note are not cleared for use;
no slot was used. Do not run emission or submission commands to reproduce this artifact.

Supporting records:

- `evidence/run_card_gems66-lidar_lane-37654dots-20261011T214803Z-a08aa21d30ba.json`
- `evidence/relief_matched.json`
- `evidence/uniqueness_gems66-lidar_lane-37654dots-20261011T214803Z-a08aa21d30ba.json`
- `evidence/uniqueness_gems66-lidar_lane-37654dots-20261011T214803Z-a08aa21d30ba-nan.json`
- `docs/review/2026-10-11-pr12-reconciliation.md`
- `docs/irregularities.html` and `IR-71-LIDAR-RAW-OVERLAP`

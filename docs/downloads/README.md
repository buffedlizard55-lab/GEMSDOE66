# Downloads

## Current file — available, but NOT cleared for submission

| | |
|---|---|
| **file** | [`gems66-h66c-scarpgap-42000-20261012T021141Z-4023a1c1ef59.tif`](gems66-h66c-scarpgap-42000-20261012T021141Z-4023a1c1ef59.tif) |
| **zip** | [`…4023a1c1ef59.zip`](gems66-h66c-scarpgap-42000-20261012T021141Z-4023a1c1ef59.zip) — 268,440 bytes |
| **sha256 (tif)** | `9bfe2d404a81f02598576000ce41ce8082475768fde5a29f346d2dadcec3d34a` |
| **sha256 (zip)** | `1564930414a31044a4fce73ce57d74dbe5289260cf7ffc9285307ba3381edd5a` |
| **size** | 378,581 bytes · 3730 × 3292 · float32 · 1 band · EPSG:32611 · 100 m |
| **emitted cells** | 42,000 (0.813 % of the 5,165,852-cell features footprint) |
| **validator** | PASS — 0 failures, 0 skipped (`gems.validate_submission`, reference `labels.tif`, features `training_features.tif`) |
| **uniqueness** | UNIQUE on 60 accessible registry rasters: surface max \|ρ\| 0.080, final dots max \|ρ\| 0.290 |
| **HOLDOUT-DTI** | 0.0979, 95 % CI [0.0623, 0.1219], instrument N, 2,355 withheld positives — **below the frozen best 0.1195** |

### Is it OK to download and submit?

- **Download: yes.** It is a real, format-clean, unique GeoTIFF. Verify the SHA-256 above.
- **Submit: no.** The scientific gate is not met. On the only holdout instrument in this
  repository that is positively rank-correlated with the owner-reported live scores, the
  candidate (0.0979) is below every frozen baseline (anderson 0.1195, h33-2-b2 0.1104,
  d28 0.1065). Two independent scientific-lead reviews are also still outstanding.

Producing this file spent **no** competition submission slot. Spending one is a separate, human
selector decision. See the [executive summary](../executive-summary.html) for the exact steps if
a selector chooses to proceed, and the
[H66-C verdict note](../review/2026-10-12-h66c-verdict.md) for the reasoning.

### Method in one paragraph

The diffused-scarp template `z = (a/2)[1 + erf(x / (2√(κt)))]` is inverted on the 2 m-computed
LiDAR descriptors: `max|z'| = a/(2√(πκt))` and `max|z''| = 0.12096·a/(κt)` give a scarp-height
proxy `a_hat = 1.5203·S²/C` and a morphologic-age proxy `κt_hat = 1.5203²·a_hat²/(4πS²)`, with
`S` the 2 m slope excess over the 30 m regional slope and `C` the 6 m-LoG curvature dipole.
Steger sub-pixel lines (TPAMI 20(2):113–125, 1998) and Frangi multiscale vesselness (MICCAI 1998,
LNCS 1496:130–137) at σ = 1.0–3.0 cells are added on that field and on the slope-detrended
elevation. Roads are removed with the official US Census TIGER 2024 road-distance raster; canals
and field edges by a four-way geometric conjunction. The field is gradient-boosted under 20 km
block holdout and emitted as a greedy packing (400 m minimum separation) with a 200 m hard /
600 m ramp **catalogue-gap gate**.

---

## Do not upload these — historical, audit-only

**H66-1:** Historical TIFF/ZIP bytes were withdrawn from the public download path and retained
only as byte-verified audit copies under `evidence/archives/h66-1/`, outside the Pages document
root and without site links. They did not pass the required holdout, leakage, complete-registry,
provenance, and exact-footprint release gates.

**H66-2:** A historical negative result; its figures are off-catalogue proxies, not
`HOLDOUT-DTI` or `ORGANIZER-CONFIRMED`. Audit artifacts are under `artifacts/h66-2/`.

**lidar_lane:** The scarp-field artifact and analysis are retained under `artifacts/lidar_lane/`
for audit only. The reported pooled gain was reversed by relief-matched evaluation; no organizer
score is established. Its density-adjusted uniqueness output does not override the raw rule: the
recorded final-dot overlap is 0.990 against an accessible registry raster, above the 0.70 stop
threshold. Only 60 rasters were compared, full organizer-registry completeness is uncertified,
and the pre-placement surface comparison is not reported.

The shared-template provenance discrepancy and the PR #12 reconciliation are recorded in
[`review/2026-10-11-pr12-reconciliation.md`](../review/2026-10-11-pr12-reconciliation.md). The
canonical run card is [`data/run-card-h66c.json`](../data/run-card-h66c.json). No
`ORGANIZER-CONFIRMED` result or cleared submission is claimed.

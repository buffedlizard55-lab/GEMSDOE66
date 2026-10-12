# No submission file is published here

**Current disposition (2026-10-12): BLOCKED / NEGATIVE.** This directory intentionally contains no current GeoTIFF or ZIP cleared for submission. The check-only input preflight found all eight required competition/cache paths absent; no native 1 m DEM, cached feature stack, cultural mask, official reference grid, or certified complete registry is available in this checkout. No experiment, holdout, candidate, download, or submission slot was used. Do not manufacture a TIFF or reuse a historical raster to fill this gap.

- Latest [three-pass review](../review/2026-10-12-review.md)
- Canonical [run card](../data/run-card.json)
- [Input preflight receipt](../../evidence/input_preflight_2026-10-12.json)
- [Mechanical release preflight](../../evidence/release_preflight_2026-10-12.json) — `download_allowed: false`

The reported portal error `Predicted values must be in range [0, 1]` is not verified as fixed for a real competition artifact because no authorized candidate or upload receipt is available. The shared writer refuses substantive out-of-range values (allowing only tiny floating-point round-off), and the shared validator tests the [0,1] rule along with the exact reference/features grid and NaN-only-outside contract. Synthetic tests passed; they are not an organizer upload or acceptance. Do not treat a local format check as release clearance.

## Historical artifacts — audit only

- **H66-1:** Historical TIFF/ZIP bytes were withdrawn from the public download path and retained only as byte-verified audit copies under `evidence/archives/h66-1/`, outside the Pages document root and without site links. They did not pass the required holdout, leakage, complete-registry, provenance, and exact-footprint release gates.
- **H66-2:** A historical negative result; its figures are off-catalogue proxies, not `HOLDOUT-DTI` or `ORGANIZER-CONFIRMED`. Audit artifacts are under `artifacts/h66-2/`.
- **lidar_lane:** The later scarp-field artifact and analysis are retained under `artifacts/lidar_lane/` for audit only. The reported pooled gain was reversed by relief-matched evaluation; no organizer score is established. Its density-adjusted uniqueness output does not override the raw rule: the recorded final-dot overlap is 0.990 against an accessible registry raster, above the 0.70 stop threshold. Only 60 rasters were compared, full organizer-registry completeness is uncertified, and the pre-placement surface comparison is not reported. Do not treat it as unique or submission-cleared.

The shared-template provenance discrepancy and the PR #12 reconciliation are recorded in [`review/2026-10-11-pr12-reconciliation.md`](../review/2026-10-11-pr12-reconciliation.md). The 2026-10-11 [release-safety review](../review/2026-10-11-release-safety.md) remains historical context; the current blocker list is the 2026-10-12 machine preflight linked above. No `ORGANIZER-CONFIRMED` result or cleared submission is claimed.

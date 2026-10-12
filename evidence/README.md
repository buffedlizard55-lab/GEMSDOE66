# Historical evidence quarantine

Files prefixed `h66_` and the `_run_s43.log` / `_run_s4b3.log` traces are preserved as historical research evidence only. Their metric-like values, counts, AUCs, candidate metadata, and raster hashes are **not** a current qualified result. They are not `HOLDOUT-DTI` values and are not `ORGANIZER-CONFIRMED` submission results.

The evidence JSON files include a top-level `evidence_disposition` that records the missing evaluator/count/95% CI and the protocol failures. In particular, the historical pipeline used full-catalogue distance before holdout scoring; did not restrict scoring to the required LiDAR-covered held-out domain; and did not implement the current buffered whole-segment design. The complete registry and official reference footprint were not available. These records must not be copied into a current run card as scores or clearance evidence.

The exploratory negative cultural-veto/proxy comparison is retained in `h66_e1_offcat.json` for traceability. It used an SGMC-derived proxy, not organizer labels or GeoDAWN data; it is unqualified and cannot be generalized to the competition test set.

`data_verification.json` is an older owner-mirror integrity record imported from the updated base branch. Its file-level disposition states that it is not organizer authentication, current input provenance, LiDAR coverage certification, a holdout result, or release clearance. Its listed raster bytes are not present in the current checkout.

## 2026-10-12 current preflight evidence

- [`input_preflight_2026-10-12.json`](input_preflight_2026-10-12.json) records the presence-only `bash scripts/fetch_inputs.sh` result: exit 2, all eight competition/cache inputs absent, and no network request, copy, authentication, or processing. It also records no native DEM, cultural mask, official grid, or complete-registry certificate.
- [`h33_owner_claim_review_2026-10-12.json`](h33_owner_claim_review_2026-10-12.json) records an owner-page statement, not an organizer score receipt. The user-supplied H33 value remains unverified and is not tied to an exact raster hash.
- [`release_preflight_2026-10-12.json`](release_preflight_2026-10-12.json) records `cleared_for_review: false` and `download_allowed: false`; it is a mechanical blocker report, not a scientific result.
- The full three-pass disposition is [`../docs/review/2026-10-12-review.md`](../docs/review/2026-10-12-review.md).

No `HOLDOUT-DTI` measurement from this review exists. A future result must include the exact evaluator version, withheld-positive count, and a 95% spatial-block confidence interval. An organizer value may be called `ORGANIZER-CONFIRMED` only when copied from a submission receipt tied to the exact artifact SHA-256. No credentials or hidden labels were used in this review.

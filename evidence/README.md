# Historical evidence quarantine

Files prefixed `h66_` and the `_run_s43.log` / `_run_s4b3.log` traces are preserved as historical research evidence only. Their metric-like values, counts, AUCs, candidate metadata, and raster hashes are **not** a current qualified result. They are not `HOLDOUT-DTI` values and are not `ORGANIZER-CONFIRMED` submission results.

The evidence JSON files include a top-level `evidence_disposition` that records the missing evaluator/count/95% CI and the protocol failures. In particular, the historical pipeline used full-catalogue distance before holdout scoring; did not restrict scoring to the required LiDAR-covered held-out domain; and did not implement the current buffered whole-segment design. The complete registry and official reference footprint were not available. These records must not be copied into a current run card as scores or clearance evidence.

The exploratory negative cultural-veto/proxy comparison is retained in `h66_e1_offcat.json` for traceability. It used an SGMC-derived proxy, not organizer labels or GeoDAWN data; it is unqualified and cannot be generalized to the competition test set.

No `HOLDOUT-DTI` measurement from this review exists. A future result must include the exact evaluator version, withheld-positive count, and a 95% spatial-block confidence interval. An organizer value may be called `ORGANIZER-CONFIRMED` only when copied from a submission receipt tied to the exact artifact SHA-256. No credentials or hidden labels were used in this review.

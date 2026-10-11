# No submission file is published here

**Download status: NOT AVAILABLE.** There is no current TIFF or ZIP cleared for submission.
Do not upload a historical H66 artifact.

This directory is intentionally empty of rasters. Two independent sessions have now tested the
native-resolution LiDAR scarp lane and both returned a **NEGATIVE** verdict:

* **H66-2** (session `arena/133c86e6`) — concordance of three independent 2 m LiDAR scarp
  attributes. Its mass-matched terrain-only control came within 1.9× of the field pooled.
  Bytes: `../../artifacts/h66-2/`.
* **lidar_lane** (session `arena/7d2c4a3b`) — Frangi / Steger / structure-tensor scarp field.
  It beats the incumbent 0.07075 vs 0.04896 on the pooled holdout, but that instrument is
  **confounded**: the truth is 59.3 % range front against a footprint that is 25.2 % range
  front, and the field is 64.3 % range front, so it matches the truth's relief prior rather
  than finding faults. De-confounded it scores 0.02638 against the incumbent's 0.02727 and
  random placement's 0.02612 — indistinguishable from both.
  Bytes: `../../artifacts/lidar_lane/`.

Both files are kept for audit. Neither has passed the release gate, and
`tests/test_site.py` fails the build if any page links a `.tif` or `.zip`.

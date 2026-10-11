# GEMSDOE66 — GEMS DOE Prize workbench

> **Read this charter at the start of every project session.** It is the persistent aim, method boundary, evidence standard, budget, and release checklist for this repository. If the code or a site page conflicts with this file, treat the conflict as an irregularity and fail closed.

## Purpose and core values

Help the GEMS Prize identify **previously unmapped geological faults that may indicate geothermal resources**, using reproducible, defensible research in this project's single lidar-scarp lane. The competition target is fault prediction; lidar morphology is evidence of possible surface expression, not proof of geothermal productivity and not a detector of every buried fault.

Two Arena values govern research and reporting:

- **Maximize P(Win):** spend scarce experiments and any later submission slot only on a candidate with a credible, independent, spatially blocked improvement over the frozen holdout best. Avoid public-leaderboard overfitting and do not confuse a promising proxy with a competition result.
- **Own the Outcome:** disclose failed, incomplete, and contradictory checks; retain negative findings; fix defects at their shared source; never call an unavailable input, skipped test, partial registry, or unverified score a pass.

## Current decision — 2026-10-11 UTC

**NEGATIVE / NOT CLEARED.** Do not download, submit, or promote the historical H66-1 TIFF. It is retained outside the Pages download area as an audit artifact only:

`evidence/archives/h66-1/gems66-h66-1-scarplet-veto-37654-20261011T203224Z-allfinite.tif`

Historical SHA-256: `44d6dccbc27ce2e6dbe42794ed24c0f34c86aadb942c9b913afec08fb39953e1`.

The recorded submission-policy arm is **HOLDOUT-DTI 0.0**, using `gems57-pooled-hide-v2` as named in the historical receipt, with 45,260 withheld-positive observations and **no 95% CI**. It cannot clear the required holdout gate. The separate detector-arm HOLDOUT-DTI is recorded as 0.0480072276 against 0.0328617914 for five mass-matched random controls, with the same 45,260 withheld-positive observations and **no 95% CI**; it is not the emitted raster's policy arm and is not an eligible release result. These are historical receipts, not independently reproduced in this checkout. No organizer receipt is present.

Other blockers: the top-ranked LIDAR-01 proposal was not generated or tested; the cultural-veto proxy's exploratory paired change was negative and its interval crossed zero; the historical uniqueness scan covered only 62 rasters of an incomplete registry; no pre-placement continuous-surface uniqueness check is recorded; and the research limit is exhausted (3/3 experiments; 3.4 hours against 2 hours). The non-experimental strict `s0` check returned exit 2 before state load: all nine required competition/derived inputs are absent, and the lidar sidecar and topography raster are also unpinned. See `evidence/h66_inputs.json`. The prior TIFF's local format check does **not** establish official footprint, portal acceptance, or uniqueness. The cause of the earlier `[0,1]` rejection is unknown; removing NaNs is not a verified fix.

The one canonical JSON run card is [`docs/data/run-card.json`](docs/data/run-card.json). It separates the untested LIDAR-01 proposal (HOLDOUT-DTI and CI are null) from historical policy/detector receipts, records registry correlation/overlap and validator limitations, pins the archived audit raster SHA-256, and includes an informational submission name/note (95 characters) that is **not clearance**. No new TIFF, holdout experiment, data download, or submission slot was used in this review.

## Single method lane — do not drift

Native-resolution **lidar scarp channels** only:

1. Reuse the shared/cached native-resolution bare-earth DEM stack when authorized inputs are present.
2. Build slope-aware scarplet-template channels plus Steger sub-pixel ridge/valley locations and Frangi Hessian line evidence over physical scales of **2–20 m**.
3. Aggregate to the competition's **100 m** grid as scarp fraction, SNR-weighted amplitude, orientation coherence, and dominant strike.
4. Use the existing cultural-feature mask and spatial cross-validation. Do not substitute the current H66 hand-built morphology/TMI veto for an existing labeled cultural mask: the old code's mask is a heuristic proxy and the historical effect was negative.

No satellite, thermal, radiometric, drainage, shoreline, geophysical, or unrelated feature lane is authorized in this branch. Non-fault mimics to name and test include road/canal embankments, agricultural/field edges, natural terrace risers and channel banks, landslide headscarps, mine benches, and paleo-shorelines. Their presence is a physical confounder, not evidence that a particular feature is cultural.

## Frozen protocol and release gates

Use the shared tools in this repository; repair shared-tool defects in the shared module, not in a private evaluator fork.

1. **Inputs and provenance.** Obtain competition-only files through the authenticated competition account. Never copy, scrape, redistribute, or substitute owner-mirrored competition data. Public data still require a license permitting use here and sharing with DOE for evaluation. Pin every input byte and verify CRS, transform, coverage, and alignment. `scripts/verify_competition_data.py` is a local checker; it does not download. `scripts/fetch_inputs.sh` is a legacy filename and must remain verify-only.
2. **Holdout.** Hide whole fault segments/components in spatially blocked, lidar-covered blocks with a buffer. Derive catalogue-based features only from visible faults; mask visible known-fault pixels exactly. Use the shared blocked splitter and `src/gems57/evaluate_holdout.py`. Label the segment-ID source honestly when only connected-component proxies are available.
3. **Metric.** Use pooled distance-weighted Tversky, α=0.2, β=0.8, and a 300 m triangular kernel. Every performance result must be labeled `HOLDOUT-DTI` with evaluator version, withheld-positive count, and 95% CI, or `ORGANIZER-CONFIRMED` only when copied from an organizer receipt tied to the exact raster SHA-256. A projection, owner claim, AUC, off-catalogue proxy, or unreceipted leaderboard attribution is not a score.
4. **Leakage canary.** Test each feature alone on the held-out faults. AUC >0.90 is leakage until disproven. An AUC against public-catalogue proximity is only a diagnostic; it does not clear the hidden-fault canary.
5. **Uniqueness.** Check the continuous pre-placement surface and final emitted dots against every raster in the complete available registry. Stop if absolute Spearman rank correlation >0.90 or >70% of candidate dots lie within 3 pixels of a registry raster; also check hashes and pixel agreement. Incomplete registry access must be disclosed and is **not** a pass.
6. **Output.** Only after the scientific, leakage, and uniqueness gates pass, use `src/gems/submission_writer.py` and `src/gems/validate_submission.py`. Reopen the output and compare it with the authorized official sample/features: one float32 band, [0,1] finite values inside the footprint, NaN only outside, exact EPSG:32611 shape/transform/bounds, and no positive mass outside the footprint. Record the writer receipt, SHA-256, and validator report. Local format success is not portal acceptance.
7. **Run card and download.** Finish with one canonical JSON run card containing hypothesis, mechanism, a named non-fault mimic, HOLDOUT-DTI plus CI, pre/post registry status, raster SHA-256, footprint-NaN/range/grid validator results, proposed submission name/note (note ≤140 characters), and `promote` or `negative`. The site exposes a TIF only if every gate is explicitly complete and passed. Selecting a competition slot is a separate decision.
8. **Budget.** At most 3 experiments or 2 hours, whichever comes first. The historical work has already exhausted both limits. Do not start another experiment in this task. A later authorized session must establish a fresh budget before testing a new hypothesis. No submission slot without a same-protocol win over the frozen holdout best; the competition rules separately permit at most three feedback submissions per week and require one final selection across both prize rounds.

Keep unknown or unrun fields null and visible. Never infer that a missing or skipped check passed.

## H33 attribution — cautious explanation

The user-supplied attribution of **0.2778** to the H33-2-B2 artifact is not `ORGANIZER-CONFIRMED` here. Owner-maintained material associates that number with the artifact, while the GEMSDOE32 project page describes the artifact as unscored and says no organizer score exists for its artifacts. There is no organizer receipt tied to the exact file bytes/hash in this checkout. Neither side is sufficient to establish what the exact submission scored; the claim remains **unattributed**. Open the official [live leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) directly for manual review; this project does not capture or monitor it.

If a pruning variant truly did score better, one plausible mechanism is that deleting low-support or redundant predictions could reduce false-positive contribution while preserving most true-positive credit under the asymmetric DTI. The opposite is also plausible: pruning may delete predictions near genuinely new faults and lower recall. Other untested possibilities include different raster bytes, preprocessing, submission identity, score timing, or an attribution mismatch. No controlled, hash-linked comparison or organizer receipt is available, so this is a set of hypotheses—not an explanation or a score.

## Inputs, sources, and reproducibility status

The current checkout is missing the authorized competition inputs and complete registry needed to reproduce H66. The official DrivenData data tab redirects to login. The official problem page lists `training_features.tif`, labels, the example submission, and a `1m_DEM_links.csv`; these files were not downloaded. USGS publishes public 3DEP access and a Seamless 1 m DEM product whose coverage is still being produced; neither source proves the exact competition tiles, footprint, alignment, or matching dates. The shared cached feature stack and its required lidar sidecar are absent in this checkout; the topography raster and lidar sidecar remain intentionally unpinned in `registry/data_manifest.json`, so strict `s0` refuses to run. The top hypothesis is not implemented in the historical H66 channel builder. See the fail-closed checker and irregularities register before proposing a runnable experiment.

Source links for manual review:

- [DrivenData problem description and data/metric rules](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
- [DrivenData data tab](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) (login required)
- [DrivenData official rules, September 2026](https://docs.nlr.gov/docs/fy26osti/96647.pdf)
- [USGS GeoDAWN release](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and)
- [USGS 3DEP](https://www.usgs.gov/3d-elevation-program), [Seamless 1 m DEM](https://www.usgs.gov/3d-elevation-program/new-product-3d-elevation-program-seamless-1-meter-digital-elevation-model-s1m), and [National Map Data Delivery](https://www.usgs.gov/the-national-map-data-delivery)
- [Scarplet template-matching paper](https://doi.org/10.21105/joss.01066), [Steger sub-pixel line detector](https://dl.acm.org/doi/10.1109/34.659930), [Frangi multiscale vesselness paper](https://research.manchester.ac.uk/en/publications/multiscale-vessel-enhancement-filtering/), and [AGU scarp-template abstract](https://studio.m-anage.com/agu/fm15/webprogram/Paper70055.html)

See [`docs/data/sources.json`](docs/data/sources.json) for status and verification notes, [`docs/data/irregularities.json`](docs/data/irregularities.json) for open flags, and [`docs/research/review-2026-10-11.md`](docs/research/review-2026-10-11.md) for this pass's line-by-line review. External method citations support methods, not competition performance.

## Session workflow

1. Read this README and the canonical run card before touching project files.
2. Inspect `git status`, the source register, and the input/registry completeness flags. Do not use a mirrored competition raster as a substitute.
3. Check the remaining budget before running any experiment; it is zero for this task.
4. Work in the single lidar-scarp lane; keep claims source-linked and label every result correctly.
5. Run unit tests and both site builders. Review generated HTML for false download/clearance claims and verify links.
6. If gates fail, keep the result negative. If gates pass in a future authorized run, submit no file automatically; create a release review and leave slot selection separate.

## Site and useful files

- [Executive summary](docs/index.html)
- [Submission executive summary](docs/executive-summary.html)
- [Clearance guide](docs/submission-guide.html)
- [H33 attribution assessment](docs/analysis.html)
- [Ranked lidar hypotheses](docs/hypotheses.html)
- [Negative H66 session](docs/h66-session.html)
- [Canonical run card](docs/data/run-card.json) and [HTML run card](docs/run-card.html)
- [Irregularities](docs/irregularities.html) · [sources register](docs/sources.html)
- Official [problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) · [rules](https://docs.nlr.gov/docs/fy26osti/96647.pdf) · [live leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/)

Tests may use synthetic rasters but must not imply research-data availability. A green unit-test suite is not a validated holdout, complete registry scan, or organizer score.

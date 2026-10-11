# PR #12 reconciliation review — 2026-10-11

**Repository:** `buffedlizard55-lab/GEMSDOE66`
**Working branch:** `arena/3ba7d764-gemsdoe66`
**PR:** [#12](https://github.com/buffedlizard55-lab/GEMSDOE66/pull/12)
**Lane:** native-resolution LiDAR scarp channels only
**Decision:** **NEGATIVE / NOT CLEARED.** This reconciliation runs no new experiment and does not alter the historical H66-2 measurement record from the newer `main` branch.

## 1. Session-start charter and scope

`README.md` was read as the session-start charter. The binding objective remains **Maximize P(Win)** by testing generalizable scarp signatures, and **Own the Outcome** by preserving provenance, negative results, uncertainty, and stop conditions. Work remains in the single native-resolution LiDAR scarp lane: slope-aware scarplet-template matching plus 2–20 m Steger/Frangi ridge/valley evidence, summarized on the 100 m grid with the existing cultural-feature mask and spatial CV.

The four ranked, same-lane hypotheses and named non-fault mimics remain in `docs/data/hypotheses.json`. The lead (`LIDAR-01`, cross-scale template/line-evidence consensus) is not implemented or evaluated. The protocol remains holdout-first: buffered whole fault segments; catalogue features only from visible faults; exact visible-fault masking; lidar-covered held-out blocks; pooled DTI with α=0.2, β=0.8 and a 300 m triangular kernel; feature-alone leakage tests; then full-registry checks and exact-grid validation. A partial registry is not a pass. No projection is reported as a score.

## 2. This review versus the inherited H66-2 record

The newer `origin/main` revision contains the prior, preregistered H66-2 experiment and its negative verdict. It remains recorded in `docs/review/2026-10-11-h66-2-verdict.md`, `evidence/h66b_*.json`, `artifacts/h66-2/`, and the nested `h66_2_experiment` object in the canonical run card. Its instrument comparisons are explicitly **proxy measurements, not scores**; they are neither `HOLDOUT-DTI` nor `ORGANIZER-CONFIRMED`. H66-2 is **NEGATIVE-NOT-PROMOTED**, has no submission receipt, and is not linked from the public site.

This PR reconciliation itself ran **zero experiments, zero holdouts, zero candidate emissions, and used zero submission slots**. It did not recompute, relabel, or overwrite any H66-2 measurement. No new candidate or scientific success is claimed.

## 3. H33-2-B2 attribution: unresolved, not causal

The H33-2-B2 score attribution remains **unverified**. No organizer receipt in this checkout ties the alleged score to the exact TIFF bytes or SHA-256, and the owner-maintained GEMSDOE32 material conflicts with the supplied attribution. Therefore neither “why it scored” nor “whether this exact artifact scored” can be established from the available evidence. Plausible mechanisms such as ranking, probability mass, masking, catalogue proximity, rasterization, or a different artifact are only hypotheses; none is a finding. Do not infer performance from an owner page, public leaderboard row, or metric proxy. See `docs/analysis.html`, `docs/data/claims.json`, and irregularity `IR-01-H33-ATTRIBUTION`.

## 4. Code review — changed uniqueness gates and retained safety stops

The code changes are limited to the shared `src/gems57` uniqueness implementation, its gate wrapper, the lane-check utility, tests, the audit-only archive, and documentation/status synchronization. The newer `scripts/run_h66.py` from `main` was retained: its historical stages stay disabled. The changes do not enable an experiment, writer, or submission path.

| File / current line range | Line-by-line review focus and conclusion |
|---|---|
| `src/gems57/uniqueness.py:1-13` | Module contract distinguishes a continuous detector surface from the final sparse emitted dots; it does not treat every positive surface pixel as a submitted dot. |
| `src/gems57/uniqueness.py:49-156` | `summarize_registry_rows` rejects unknown phases, recomputes stale threshold flags (including negative high-magnitude correlations), applies **absolute Spearman |ρ| > 0.90** and byte/decoded-pixel identity to both phases, applies >70% within-3-pixel overlap only to emitted dots, and makes malformed metrics/incomplete scans fail closed. A clean accessible subset is explicitly not a full pass: `unique` requires an organizer-complete certificate; surface reports suppress dot-count/overlap fields; Jaccard remains diagnostic. |
| `src/gems57/uniqueness.py:159-240` | Incremental audit merging checks candidate identity, limits, phase, source errors, and completeness before merging rows; an extension cannot turn a partial base scan into a complete scan, and full uniqueness remains blocked unless both inputs preserve explicit organizer-registry completeness. |
| `src/gems57/uniqueness.py:275-382` | `compare_array_to_registry` validates phase, grid/footprint and indexed raster identity; computes candidate/registry decoded hashes and full-footprint rank comparison; makes 3-pixel overlap inapplicable for `surface`; catches per-source failures; and only treats the registry as complete when the manifest has `organizer_registry_complete: true` plus an integer expected raster count matching the indexed entries. A surface array is not a file, so its decoded-array hash is recorded rather than pretending it has an emitted-file hash. |
| `src/gems57/uniqueness.py:458-591` | The compatibility `two_phase_summary` handles null surface-overlap fields, uses absolute Spearman, keeps density classification diagnostic only, applies emitted-dot overlap across all indexed rasters, and cannot return a full pass without explicit organizer-completeness plus matching count. |
| `src/gems57/gates.py:150-183` | Shared wrapper rejects partial legacy `priors`, requires a registry index, pins the reference grid, maps the compatibility `dots` label to emitted-dot policy, and forwards progress/report metadata. Its `ok`/`complete_registry_pass` are false without the explicit organizer-complete certificate; a clean accessible subset is reported separately. |
| `scripts/lane_check.py:1-25, 65-159` | Standalone aligned-raster diagnostic now uses Spearman rank correlation and its absolute threshold, reports exact pixel/hash data, applies the forward 3-pixel overlap only to emitted dots, and leaves empty/constant comparisons inconclusive. |
| `tests/test_uniqueness.py:1-223` | Deterministic checks cover dense surface behavior, emitted-dot overlap, negative high-magnitude correlation, exact decoded-pixel identity, stale cached flags, malformed metrics, invalid phases, safe two-phase summaries, and ensure an accessible subset without an explicit organizer-complete/count certificate cannot pass. |
| `tests/test_lane_check.py:60-100` | The utility tests assert the rank statistic and JSON-safe inconclusive result. |
| `scripts/run_h66.py:47-52, 515-537` and `tests/test_run_h66_safety.py:1-38` | The current `main` runner has historical stages disabled. Regression tests call each legacy stage and CLI stage name only to verify fail-closed behavior; they do not load inputs or create artifacts. |
| `registry/template_provenance.json` | The recorded per-file comparison now finds 19/23 byte-identical files: the two `anatomy.py`/`metric.py` differences are inherited from newer `origin/main`, while this PR changes shared `uniqueness.py`/`gates.py`. The file formerly referenced `registry/template_pin.json`, which is absent from `origin/main`; no live upstream revision/tarball comparison was performed. No external owner-maintained template PR or merge is claimed. |

The registry remains incomplete. The historic audit found only 62 of 655 expected rasters available to one scan; H66-2's recorded 21-file comparison likewise does not constitute a complete registry pass. No current continuous-surface or emitted-dot scan was run in this reconciliation.

## 5. Input check and H66-1 archive

The branch's strict `s0` input/pin check ran once before integrating newer `main`. Its preserved result is `evidence/h66_inputs_s0_review.json`: exit code 2, all 9 required local roles absent, missing pins for `external/lidar_scarp_features.json` and `external/topo_10m_derived_100m_u8.tif`, no hash mismatch, and no pin conflict. It returned before loading data; no experiment followed. Because `main` intentionally disables the legacy runner, this is a dated historical preflight snapshot, **not current runner output** and not evidence that any input is now available.

The three H66-1 TIFF/ZIP variants retain their exact SHA-256 identities under `evidence/archives/h66-1/`. The files are byte-verified against the canonical run card, reside outside the Pages document root, and are not linked or exposed in `docs/downloads/`. Archive retention changes neither clearance nor the known `[0,1]` portal-rejection uncertainty. See `IR-67-H66-1-ARCHIVE` and `docs/downloads/README.md`.

## 6. Canonical negative run card

`docs/data/run-card.json` remains the single canonical machine-readable card; `registry/run_card.json` and `docs/runcard.json` are synchronized mirrors. Its current LIDAR-01 entry records:

- **Hypothesis/mechanism/mimic:** cross-scale native LiDAR scarp shape plus persistent line evidence; named primary mimic is a fluvial terrace riser, with channel-bank and landslide controls.
- **HOLDOUT-DTI:** value, evaluator version, withheld-positive count, and 95% CI are all null; no qualifying holdout exists.
- **Leakage and uniqueness:** not validated; both phases are blocked by missing candidate and incomplete registry. Thresholds remain |ρ| > 0.90, and >70% within 3 pixels for final dots only.
- **Current raster/SHA-256:** file and hash are null because no LIDAR-01 candidate exists. Historical hashes remain itemized and linked only to audit archive paths.
- **Current validator:** not run; NaN-outside, [0,1], and CRS/shape/transform checks are not established for a LIDAR-01 candidate. H66-2's local preflight is separately and explicitly recorded: EPSG:32611, shape 3730×3292, locally recorded transform, min/max [0,1], but 0 NaNs and zeros outside the footprint. That all-finite output does **not** satisfy the required NaN-only outside-footprint contract and is not organizer acceptance.
- **Submission name/note:** a 36-character name and a 103-character note are marked **PROPOSED ONLY**; no candidate file exists and neither is cleared for use.
- **Decision:** `promote: false`, `promotion_decision: "negative"`; no slot used.

The static site was regenerated from the canonical sources, states there is no download, shows the proposal text as unusable planning metadata, and does not add artifact links. `docs/data/run-card.json` is the only canonical card; the H66-2-specific card remains a separate historical experiment record, not a competing current status.

## 7. Source links and evidentiary limits

The inherited main audit and `docs/data/sources.json` contain the detailed source register. These links are retained for manual review; this reconciliation does not claim a new web review:

- [Official DrivenData problem description](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) — task and distance-weighted Tversky description; not a score receipt.
- [Official competition data tab](https://www.drivendata.org/competitions/306/competition-doe-gems/data/) — redirected to login in the recorded review; no credentials used and exact tile inventory remains unknown.
- [NLR-hosted GEMS Prize Official Rules PDF](https://docs.nlr.gov/docs/fy26osti/96647.pdf) — only partial PDF chunks were reviewed; chunk 1 failed, so this is not a complete rules review.
- [DrivenData Terms of Use](https://www.drivendata.org/termsofuse/) — review remains partial; no legal conclusion is made.
- [USGS 3DEP](https://www.usgs.gov/3d-elevation-program), [USGS GeoDAWN](https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and), and [EPSG:32611](https://epsg.io/32611) — product/CRS context only; do not prove exact competition tile coverage or candidate alignment.
- [Scarplet JOSS article](https://joss.theoj.org/papers/10.21105/joss.01066), [Steger paper](https://dl.acm.org/doi/10.1109/34.659930), [Frangi publication record](https://research.manchester.ac.uk/en/publications/multiscale-vessel-enhancement-filtering/), and [AGU slope-aware scarp-template abstract](https://studio.m-anage.com/agu/fm15/webprogram/Paper70055.html) — method context, not competition-performance evidence.
- [Owner-maintained GEMSDOE32 repository](https://github.com/buffedlizard55-lab/GEMSDOE32) — non-organizer attribution context only; it cannot confirm a score.

## 8. Irregularities and three-pass review

- **Pass 1 — claims/evidence:** retained the latest main source audit and H66-2 negative record; checked the H33 attribution caveat; distinguished proxy measurement, historical validation, holdout evidence, and organizer receipts. No unsupported score or submission claim is added.
- **Pass 2 — code/merge:** reviewed the phase-aware uniqueness additions above; chose newer `main` for the README charter, H66-2 record, canonical research state, site data, and deliberately disabled historical runner; retained this branch's audit-only H66-1 bytes and shared uniqueness tests. No “ours” overwrite of newer H66-2 evidence was used.
- **Pass 3 — repository checks:** `./.venv/bin/pytest -q` passed **88 tests**; `python -m compileall -q scripts src tests` and `bash -n scripts/fetch_inputs.sh scripts/download_competition_data.sh` passed; all **37 repository JSON files** parsed. The site builder ran and the site tests confirmed no TIFF/ZIP download links, no DrivenData competition subpage hyperlinks, and resolving local links. The H66-1 archive hashes/ZIP integrity are tested. `scripts/run_h66.py --help` returned safely; invoking its current `s0` CLI exited 2 with the disabled-stage message and left `evidence/h66_inputs.json` byte-identical. These are offline/repository checks only—not a scientific holdout, organizer score, complete registry, or official-grid clearance. Final `git diff --check` is recorded after staging; GitHub CI and mergeability are checked before merge, and the final merge result is verified and reported after the operation.

Current relevant irregularities are `IR-01-H33-ATTRIBUTION`, `IR-03-HOLDOUT-DESIGN`, `IR-05-SHARED-WRITER`, `IR-06-REGISTRY-COVERAGE`, `IR-07-DATA-ACCESS`, `IR-10-INDEPENDENT-REVIEWS`, `IR-66-RELEASE-01`, `IR-67-H66-1-ARCHIVE`, `IR-68-PREMERGE-S0-SNAPSHOT`, `IR-69-UNIQUENESS-PHASE`, and `IR-70-TEMPLATE-PROVENANCE`. The local shared-package correction is documented, but an external template review/merge remains outstanding; its exact current source revision also remains unverified. In particular, the all-finite-versus-NaN-outside release-policy disagreement is resolved conservatively: **no file is cleared or linked**.

## 9. Unfinished gates

No experiment, holdout, candidate emission, public download, or submission slot should be added to this PR. Before any future promotion, obtain authorized inputs and provenance; have two independent scientific leads review the ranked same-lane lead and mimics; use the canonical shared buffered whole-segment holdout/evaluator/writer; run feature-alone canaries; report only correctly labeled `HOLDOUT-DTI` with version/count/95% CI or `ORGANIZER-CONFIRMED` from a receipt tied to the exact artifact; pass full-registry pre-surface and final-dot uniqueness; verify hash/pixel agreement and official CRS/shape/transform/footprint with NaN only outside; and beat the frozen valid holdout best before a separate selector considers any competition slot.

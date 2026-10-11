# GEMSDOE66 — native-resolution fault-scarp research

> **Session-start rule:** read this entire README before doing any project work. It is the standing brief, evidence policy, and safety gate for every later session.
>
> **Current decision (2026-10-11 UTC): NEGATIVE / STOP.** This checkout has no competition data, cached lidar features, shared evaluator/writer, cultural-feature mask, registry rasters, or submission validator. No holdout was run and no submission TIFF was generated. There is **no file that is safe to download or submit**. Do not substitute or copy a sibling repository's raster.

## Mission

Develop an auditable method for identifying **geological faults that may indicate geothermal resources** in the GeoDAWN region. The competition target is fault prediction, not direct detection of geothermal vents. This work is restricted to one experimental lane: native-resolution lidar scarp channels. A lidar scarp is evidence of a surface expression; a lidar-only method cannot find every buried fault or establish geothermal productivity.

The project aims to improve the probability of winning by learning from prior results, testing a falsifiable geological mechanism, and protecting the limited submission budget. We own the outcome: a negative, well-documented gate is preferable to an unsupported score claim or an invalid upload.

## Standing method brief — read before every experiment

For high-prior tiles, use the **existing shared template's cached feature stack** and compute the prescribed native-resolution lidar evidence:

1. **Slope-aware scarp templates:** template-match the 1 m GeoDAWN/3DEP DEM for scarp amplitude, relative morphologic age, orientation, and signal-to-noise ratio. The slope-aware extension is motivated by Sare and Hilley's 2015 AGU abstract on scarps with finite initial slope and non-horizontal surfaces; do not claim that the extension or a result has been reproduced until the shared implementation and data are present.
2. **Sub-pixel line evidence:** Steger ridge/valley line responses and Frangi multiscale Hessian line measures on a slope-detrended surface, at the scales specified by the project brief.
3. **100 m aggregation:** scarp-pixel fraction, SNR-weighted amplitude, structure-tensor orientation coherence, and dominant strike.
4. **Confounder masking:** apply the existing cultural-feature mask (roads, canals, and field edges). Do not invent a replacement mask in this checkout.
5. **Evaluation:** spatially blocked hide-and-recover validation, with whole fault segments withheld with a buffer. Derive every catalogue-based feature from visible faults only; mask visible faults pixel-exactly; score pooled distance-weighted Tversky (DTI) using the competition metric. Test each feature alone first; an AUC above the pre-registered leakage threshold is leakage until explained.
6. **Geographic gate:** a gain must occur on lidar-covered holdout blocks and must not be confined to range fronts.
7. **Uniqueness gate:** compare the continuous surface before placement and the final dots against the full raster registry. If the pre-registered correlation or three-pixel overlap limit is exceeded, log a duplicate and stop; do not publish it as a candidate.
8. **Output gate:** only after the science and uniqueness gates pass, use the shared `submission_writer.py` and `validate_submission.py`. Re-open the written bytes and verify one float32 band, EPSG:32611, the exact template shape/transform/bounds, finite in-footprint values in `[0, 1]`, and NaN only outside the footprint. Record a SHA-256 and pixel-agreement audit against prior rasters.
9. **Submission policy:** the project site must make it unmistakable whether a file is cleared to download and submit. A file is not cleared by a local format check alone. Promotion to a competition slot is a separate selector decision; never upload automatically.
10. **Budget:** stop at the stated experiment/time limit. Do not spend a competition slot on a candidate that has not beaten the frozen holdout best. A projection is never reported as a score.

**Frozen protocol values (from the user brief; these are thresholds/parameters, not score claims):**

- Compute the lidar operators at **2–20 m** and aggregate to **100 m** cells.
- Spatial holdout uses the official distance-weighted Tversky specification: **α = 0.2**, **β = 0.8**, and a **300 m** triangular kernel. These are metric parameters, not measured DTI.
- Duplicate stop thresholds: surface rank-correlation **> 0.90** or more than **70%** of final dots within **3 px** of a registry raster. Check both before placement and after final emission.
- Leakage canary: test every feature alone; an AUC **> 0.90** is treated as leakage until explained.
- Each reported holdout result must include a **95% CI** and the number of withheld positives. A score without those fields is not a compliant `HOLDOUT-DTI` result.
- End each run with the prescribed JSON card; the submission note must be at most **140 characters**.
- Stop at **3 experiments or 2 hours**, whichever comes first. The official rules separately limit feedback submissions to **3 per week** and require one final selection across the prize rounds.

These numeric values are labeled here as **USER-PROTOCOL THRESHOLDS** or **OFFICIAL METRIC/RULE SPECIFICATIONS**; they are not measured results. Keep parameters frozen before running an experiment and identify which values are official competition specifications versus protocol thresholds.

## Evidence and score labels

Every score claim must be one of:

- **HOLDOUT-DTI** — name the evaluator version, number of withheld positives, and 95% confidence interval. State that it is a proxy, not a competition score.
- **ORGANIZER-CONFIRMED** — transcribe from the relevant official submission receipt. A score shown in a sibling repository, an owner-maintained site, or an unreceipted leaderboard attribution is not proof that a particular TIFF produced it.

Label other factual claims by provenance as appropriate: official source, peer-reviewed literature, local measurement, owner-reported, user-provided, inference, or unverified. Never convert an estimate or projection into a score. Preserve irregularities instead of quietly correcting or omitting them.

## H33-2-B2 and prior-results caution

The prompt attributes a score of `0.2778` to the GEMSDOE32 H33-2-B2 TIFF. That attribution is **not established by an organizer receipt in this checkout**. The GEMSDOE32 page describes that particular artifact as unscored and distinguishes its model projection from an organizer score. A separate sibling page reports an association between an official leaderboard row and H33 as owner-reported. Treat the attribution as unverified until the exact submission receipt and file hash are matched.

The H33 page describes a post-processing change to an earlier dotted field: removing points close to the mapped catalogue. That is a plausible way to alter false-positive mass under a distance-weighted metric, but it does not demonstrate why any private score was high, nor that the candidate caused the claimed score. See [the source reconciliation](docs/decision-log.md). The official live leaderboard is the only current source for public standings; this repository does not mirror it because DrivenData's published Terms of Use restrict automated monitoring and manual copying without prior written consent.

## Starting-checkout inventory and blockers

At session start the tracked checkout contained only this README. The following shared tools and assets were **not present**:

- official competition feature/label/example-submission rasters and the competition's 1 m DEM link table;
- the template's cached lidar feature stack and existing cultural-feature mask;
- `evaluate_holdout.py`, `submission_writer.py`, and `validate_submission.py`;
- a registered prior-raster archive and the range-front/block masks required for the gates;
- any model, trained weights, generated raster, submission receipt, or site.

The official DrivenData data page resolves to a login page in this environment. No competition credentials are available here, and credentials must never be requested in chat, stored in the repository, or used to bypass the access control. The official USGS National Map 3DEP 1 m DEM collection is a potential public source, but the exact tile set, coverage, and bytes for the required study footprint have not been acquired or verified in this session. The official competition link table remains the preferred footprint manifest once lawfully available.

Because these blockers prevent the required holdout, leakage canary, registry comparison, byte-level TIFF validation, and submission receipt, the current run card is negative. The site intentionally has no TIFF download link. This is not a claim that a candidate was rejected on measured DTI; it means the experiment could not be run.

## Project artifacts

- [Project site](docs/index.html) — status and research entry point.
- [Executive summary and upload instructions](docs/executive-summary.html) — explicitly says no file is currently cleared.
- [Ranked hypotheses](docs/hypotheses.md) — four testable proposals, costs, mimics, and data status.
- [Evidence ledger](docs/evidence.md) and [sources for manual review](docs/sources.md).
- [Decision log](docs/decision-log.md) and machine-readable [run card](docs/evidence/run-card.json).
- `scripts/audit_site.py` checks that the site stays fail-closed while the run card is negative; it is **not** a submission validator or holdout evaluator.

A GitHub Pages workflow is included. At review start, the repository was still configured for legacy Pages from the `main` root and its public URL rendered only the README. The new Actions-based site is not considered published until the Pages build type is switched and a deployment succeeds; the existence of workflow files alone is not evidence that the site is live.

## Core values

**Maximize P(Win).** Make decisions by weighing expected value, evidence quality, risk, and scarce submission opportunities. No lottery-ticket uploads, no overfitting to stale leaderboard snapshots, and no unsupported performance projections.

**Own the Outcome.** Report blockers, errors, negative results, and uncertain evidence end to end. When a shared tool is available and demonstrably wrong, fix it in the shared template rather than creating a private fork. Preserve a reproducible record of every correction.

## Start-of-session checklist

1. Read this README and review `git status` before changing anything.
2. Inspect whether the shared template, data, evaluator, writer, cultural mask, and raster registry are actually mounted; do not infer their presence from an old prompt or another repository.
3. Re-verify official sources and the current access/terms restrictions.
4. Preregister hypotheses and controls before an experiment; count experiments against the explicit budget.
5. Run the holdout and all uniqueness/format gates before publishing any download or considering a slot.
6. Update the evidence ledger and run card with measured values only. If a gate cannot run, leave its value null and record why.

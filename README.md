# GEMSDOE66 — native-resolution lidar-scarp research

> **Read this file before each session.** It is the standing project charter, protocol, and safety gate.
>
> **Current decision (2026-10-11 UTC): NEGATIVE / STOP.** The shared metric, holdout primitives, writer, validator, and registry-comparison tool are now present in this branch after reconciling `origin/main`. The competition rasters, cached lidar feature stack, cultural mask, complete prior-raster registry, and end-to-end holdout evaluator are not present. No lidar feature, holdout, leakage canary, registry comparison, or TIFF was produced. **There is no file cleared to download or submit.**

## Mission and lane boundary

Develop an auditable method for predicting geological faults that may indicate geothermal resources in the GeoDAWN region. The competition target is fault prediction, not direct detection of geothermal vents; a lidar-only method detects possible surface expression and cannot establish geothermal productivity or find every buried fault.

This branch stays in one experimental lane: **native-resolution lidar scarp channels**. Do not substitute satellite, thermal, radiometric, drainage, shoreline, or unrelated feature lanes. Candidate signals are computed at **2–20 m** scales and aggregated to the competition's **100 m** grid. The currently leading proposal is a slope-aware scarp-template field combined with Steger ridge/valley and Frangi multiscale line evidence. It is a hypothesis only—not a result or score.

## Frozen experiment protocol

Use the existing shared feature stack, masks, evaluator, writer, and validator if present. Fix a shared-tool defect in place; do not privately fork or silently replace a missing shared component.

1. **Input and features:** use the official competition tiles/manifest and shared cached lidar stack when available. Compute slope-aware scarp-template channels and 2–20 m Steger/Frangi line evidence; aggregate to 100 m. Apply the existing cultural-feature mask. Do not invent a replacement mask or silently substitute DEM coverage.
2. **Holdout:** assign whole fault segments to spatially blocked folds, with a buffer. Derive all catalogue-based features only from visible faults and pixel-exactly mask visible faults. Evaluate only lidar-covered held-out blocks; report performance separately for range-front and non-range-front strata. A catalogue-fault holdout is a proxy for the competition's *new-fault* labels, not a test-score estimate.
3. **Metric:** use pooled distance-weighted Tversky (DTI), with **α = 0.2**, **β = 0.8**, and a **300 m triangular kernel**. A score must be labeled `HOLDOUT-DTI` and include evaluator version, withheld-positive count, and 95% CI. Do not call projections or owner-reported claims scores.
4. **Leakage canary:** test each feature alone. A holdout AUC **> 0.90** is leakage until disproven.
5. **Uniqueness:** compare the continuous pre-placement surface against every registry raster; compare final emitted dots against every registry raster. Correlation **> 0.90** or **>70%** of candidate dots within **3 px** means duplicate/lane drift: stop. Record hashes and exact pixel agreement where applicable. A missing or incomplete registry is not a pass.
6. **Output:** only after the science, leakage, and uniqueness gates pass, use the shared `submission_writer.py` and `validate_submission.py`. Reopen the output and verify float32, one band, EPSG:32611, exact reference shape/transform/bounds, finite in-footprint values in `[0,1]`, and NaN only outside the footprint. Record SHA-256, validator output, and pixel agreement.
7. **Run card and release:** finish each experiment with `docs/data/run-card.json` (hypothesis, mechanism, named non-fault mimic, holdout/CI, registry checks, raster hash, validator, submission name/note, verdict). A note must be at most **140 characters**. Offer a one-click file only when the gate is met; otherwise keep the status negative. Slot selection is a separate manual decision.
8. **Budget:** stop after **3 experiments or 2 hours**, whichever comes first. Do not use a submission slot unless the candidate beats the frozen best holdout. The organizer's weekly feedback cap is separate from this research budget.

These values are protocol thresholds or published competition specifications, not measured results. Freeze parameters before any experiment. Every unknown or unrun field stays explicitly unknown/null in the run card.

## H33 attribution: evidence boundary

The user-supplied `0.2778` attribution to GEMSDOE32's H33-2-B2 artifact is **not organizer-confirmed in this checkout**. The GEMSDOE32 project page describes the artifact as unscored, distinguishes a model projection from an organizer score, and says it has no organizer score for its artifacts. A sibling page's association is owner-reported. No organizer receipt matched to the exact TIFF bytes/hash is present here, so neither attribution nor causation is established.

A possible mechanism—not a finding—is that H33-2-B2's described removal of predictions near mapped catalogue faults reduced unsupported false-positive mass while preserving credit for new faults. It could also remove useful nearby predictions. No local controlled comparison exists, so we cannot explain why H33 received any organizer result or claim that it did. The live official leaderboard is linked directly for manual review; this repository does **not** scrape or mirror it.

## Current inventory and blockers

The synchronized repository now contains shared project primitives:

- `src/gems/metric.py`: DTI implementation and formula-level tests; its distance/nodata/epsilon assumptions are documented in `docs/research/metric-derivation.md`.
- `src/gems/holdout.py`: fault-component and spatial-block splitters.
- `src/gems/submission_writer.py` and `src/gems/validate_submission.py`.
- `scripts/lane_check.py`: registry correlation and emitted-dot overlap checks.
- `scripts/verify_competition_data.py`: reports whether official inputs exist; it does not download them.
- `scripts/build_site.py`: builds the static Pages site from `docs/data/*.json`.

Still unavailable in this repository: official competition rasters and 1 m DEM-link CSV; the template's cached lidar feature stack; the existing cultural-feature mask; an end-to-end `evaluate_holdout.py`/confidence-interval runner; range-front masks; and the complete prior-raster registry. The shared metric and splitters are **not** a substitute for the missing evaluator, features, labels, or registry. The official data tab is login-gated. The 3DEP 1 m product is publicly listed in principle, but the exact required tiles, coverage, alignment, and bytes have not been obtained or verified. No external mirror is used. For any future external input, use only free official public sources and verify the exact files/coverage are obtainable before proposing them as runnable; competition-only materials must come through authorized organizer access.

The holdout, canary, uniqueness checks, competition-raster validation, and submission writer have not been run on a candidate. No holdout experiment or submission slot was used. This is a **blocked negative result**, not evidence that the proposed method has failed on measured DTI. No TIFF is offered.

## Sources and current site

- [Executive summary](docs/index.html)
- [Submission guidance](docs/submission-guide.html)
- [H33 attribution analysis](docs/analysis.html)
- [Ranked lidar hypotheses](docs/hypotheses.html)
- [Run card](docs/run-card.html) and [machine-readable card](docs/data/run-card.json)
- [Sources register](docs/sources.html), [irregularities](docs/irregularities.html), and [metric derivation](docs/research/metric-derivation.md)
- [Official live leaderboard](https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/) — direct link only; no copied table or monitoring.

The Pages source is currently `main` at the repository root. Root `index.html` redirects to `docs/index.html`; `.nojekyll` leaves the generated static pages untouched. The site is generated by `python scripts/build_site.py` and checked by CI. Do not claim a newly changed site is live until the Pages deployment is verified.

## Local checks

The current synthetic/unit and site suite reports **62 passed**; these tests do not evaluate competition features or labels. The data checker reports all official raster roles missing and exits **2**, as expected for this login-gated checkout. No end-to-end holdout or candidate validator run is claimed.

```bash
python -m pip install -e ".[test]"
pytest -q
python scripts/build_site.py
python scripts/verify_competition_data.py   # expected exit 2 while required files are absent
```

Competition data and generated model artifacts stay out of git (`data/`, `outputs/`, `runs/`, `*.tif`, and model/array files are ignored). Never ask for, store, or bypass competition credentials.

## Core values

**Maximize P(Win).** Weigh evidence, expected value, risk, and scarce submission opportunities. No lottery-ticket uploads, stale-board chasing, or unsupported projections.

**Own the Outcome.** Report blockers, tool defects, negative results, and uncertainty end to end. Reuse shared tools and fix them in place when demonstrably wrong. Preserve a reproducible record of every correction.

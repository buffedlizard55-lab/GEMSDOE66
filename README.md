
# GEMSDOE66 — native-resolution lidar-scarp research

> **Read this file before each session.** It is the standing project charter, protocol, and safety gate.
>
> **Current decision (2026-10-11 UTC): NEGATIVE ON THE HEADLINE MECHANISM — artifact delivered for audit, not promoted.**
> A measured run now exists in this branch: the lane's scarplet-channel gate **passed** on the registered holdout
> (HOLDOUT-DTI 0.048007 vs 0.032862 mass-matched random; 45,260 withheld positives; off-range-front 0.040739) and its
> cultural-veto gate **failed** (−1.0e-5 DTI, paired block-bootstrap CI crossing 0). One format-validated, registry-unique
> TIFF is therefore offered **for download and audit only** — `docs/downloads/gems66-h66-1-scarplet-veto-37654-20261011T203224Z-allfinite.tif`,
> sha256 `44d6dccbc27ce2e6dbe42794ed24c0f34c86aadb942c9b913afec08fb39953e1`. **Zero submission slots used; no score projected.**
> Site: <https://buffedlizard55-lab.github.io/GEMSDOE66/> → `docs/index.html` (summary), `docs/h66-session.html` (this run),
> `docs/executive-summary.html` (five-step how-to-submit incl. why the old `[0, 1]` rejection cannot recur).


## Standing Project Prompt and Charter

> **Read this prompt every time we work on the project as a starting point** to make sure we are building what we are aiming for and have a strong base to continue building and improving on making something useful for everyday use. It solves the problem of having to manually check everything ourselves and maintains an up-to-date current feed.

```text
Review the repo. 

THE FOLLOWING IS THE HIGHEST URGENCY AND MUST BE FOLLOWED!

MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION. DO NOT COPY A PREVIOUS SUBMISSION UNLESS IT'S FOR LEARNING AND EDUCATION. BUT WE MUST GENERATE A UNIQUE TIF SUBMISSION. IT MUST BE OBVIOUS WHETHER IT IS OK TO DOWNLOAD AND SUBMIT THE GENERATED TIF SUBMISSION.

There should be an easy to download submission tif file as described by the prompt. Read the entire prompt.

Native-resolution lidar scarp channels. The 100 m stack discards the subtle scarps visible in the 1 m GeoDAWN lidar, which plausibly is evidence geologists use to add faults. On high-prior tiles first, compute two sets of features. (i) scarplet template matching (Sare & Hilley, JOSS 2018, doi:10.21105/joss.01066), which returns amplitude, relative age, orientation and SNR from a GeoTIFF DEM, extended with slope-aware scarp templates (AGU 2015 poster T31A-2838, tested in Surprise Valley). (ii) Steger sub-pixel ridge/valley lines (IEEE TPAMI 20(2):113–125, 1998) and Frangi multiscale Hessian line measures (MICCAI 1998, LNCS 1496:130–137) at 2–20 m scales on a slope-detrended surface. Aggregate to 100 m cells as scarp-pixel fraction, SNR-weighted amplitude, structure-tensor orientation coherence and dominant strike. Mask roads, canals and field edges with the existing cultural-feature mask, then retrain under spatial CV. Gate: DTI gain on lidar-covered holdout blocks that is not confined to range fronts. Finish: normalize to [0,1]; write a float32 EPSG:32611 100 m GeoTIFF (NaN only outside the footprint); pass validate_submission.py; run a hash/pixel-agreement check against all prior rasters; offer the download only if the gate is met, else log the negative result.

PARALLEL-RUN PROTOCOL — read first. This session is one of several running from this same prompt.

1. LANE. Your lane is the single method paragraph below. Stay inside it. If your raster's rank-correlation with any registry raster exceeds [0.90], or more than [70%] of your dots fall within 3 px of one registry raster's dots, you have drifted into another lane: log it as a duplicate and stop. Check this on the surface before placement AND on the final dots.

2. REUSE, DON'T REBUILD. Use the template's cached feature stack, evaluate_holdout.py and submission_writer.py. Holdout = hide-and-recover: withhold whole fault segments with a buffer, derive every catalogue-based feature only from the visible faults, mask visible faults pixel-exactly, score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel). If a shared tool is wrong, fix it once in the template and report it; never keep a private fork.

3. LABEL EVERY NUMBER as HOLDOUT-DTI (evaluator version, number of withheld positives, 95% CI) or ORGANIZER-CONFIRMED (copied from a submission-page receipt). A projection is never written as a score.

4. LEAKAGE CANARY. Test each feature alone on the holdout before trusting any result. AUC above [0.90] means leakage until proven otherwise.

5. RUN CARD. End with one JSON card: hypothesis; mechanism; the named non-fault process that could mimic it; holdout DTI + CI; correlation/overlap vs registry; raster sha256; validator output (no NaN inside the footprint, values in [0,1], CRS/shape/transform match); submission name + note of at most 140 characters; verdict promote / negative. Negative results are deliverables.

6. BUDGET. Stop after [3] experiments or [2] hours. Do not pick submissions: promotion to a real slot is a separate selector step, within the weekly cap shown on the submission page.

The following sites should serve as a starting point for understanding how to generate TIF submissions. These websites are researched, and tested and have generated TIF submissions. But we need to generate high scoring submissions.

Current competition leaderboard GEMSDOE high score: 0.3774 / 0.3195
Highest score from GEMDOE site where submission TIF is downloaded from:
https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html
h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros: 0.2778

Before implementing, generate 3–5 candidate geological hypotheses we haven't tried yet, each naming: the specific layer(s) involved, the physical signature being targeted (e.g., an edge-detection or curvature transform), why it should catch a fault missing from the USGS/INGENIOUS catalogue rather than one already in it, and how it differs from anything already implemented in this repo. Rank them by expected DTI improvement and implementation cost. Validate the top candidate on our spatially-blocked holdout set before touching a weekly submission slot.

Core Values:
- Maximize P(Win)
- Own the Outcome

Portal Submission Requirements:
- Format: Single-band GeoTIFF (.tif) or .zip containing single GeoTIFF.
- Range: Predicted values must be in range [0, 1].
- Bounds: EPSG:32611, 3730x3292, transform matching sample_submission.tif.
- Note: At most 140 characters.
```

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

---

# Session H66-1 (this run) — measurements, artifact, reproduction

## 1 · What this repository is


A self-contained, re-runnable experiment lane for the GEMS Prize, built on the shared template
(`60GEMSDOE`) without forking it:

| path | role |
|---|---|
| `src/gems57/` | vendored **byte-identical** (23/23 files, hash-verified) — official grid, DTI metric, hide-and-recover holdout, validator, gates, uniqueness, emit |
| `src/gems66/spec66.py` | decode of the 12-band 2 m LiDAR stack back to **physical units** using the build sidecar's quantisation rule |
| `src/gems66/channels66.py` | the lane's four named aggregates + scarplet SNR + relative age + the cultural-feature veto |
| `scripts/run_h66.py` | stages `s0…s5` (verify → channels → E1 → spatial CV → holdout → artifact) |
| `scripts/verify66.py` | on-disk validator + registry scan (ρ, 3-px overlap, mass-matched-random correction) |
| `scripts/write_run_card.py` → `registry/run_card.json` | the rule-5 card; the site renders **from** it, so no number is hand-typed |
| `scripts/build_site66.py` → `docs/` | the GitHub Pages site |
| `evidence/h66_*.json` | every measurement, written before the next stage starts |

`docs/` and the small receipts are committed; `data/` and `registry/rasters/` are **not** (100 MB GitHub cap) —
restore them with `bash scripts/fetch_inputs.sh`, which fails closed on any digest mismatch.

## 2 · Result of this session (one paragraph, all numbers tagged)

The scarplet channel set **passed** the lane's holdout clause — HOLDOUT-DTI **0.048007** vs **0.032862** for five
mass-matched uniform-random dot sets on the identical registered protocol (single pooled run of gems57
hide-and-recover; 45,260 withheld positive pixels; no CI claimed for the level because no replicate arms were run),
and **0.040739** restricted to cells off the range-front proxy, so the gain is not confined to range fronts
**[measured-here]**. On the population-matched off-catalogue instrument (USGS SGMC faults >300 m from the
catalogue inside the LiDAR-covered footprint) the emission reaches DTI **0.18796** with **0.0764** credit/dot vs
**0.09028** for mass-matched random — a 2.08× concentration of real, unmapped fault trace **[measured-here]**.
The lane's *headline* mechanism, the cultural-feature veto, is a clean **negative**: it removed 28 of 37,654
top-ranked dots, moved the instrument by **−1.0e-5** DTI (paired 20 km block bootstrap CI
[−1.5e-5, +6.5e-6], P(positive)=0.129), added **0.00000** AUC to the spatial-CV retrain, and received a
**positive** logistic coefficient (1.39, 1.59 in the two usable folds) — valley-floor cultural scarps co-locate
with range-front faults instead of diluting them. Uniqueness vs the 62 rasters physically present:
|ρ|max **0.0196**, worst 3-px overlap **0.5099** (excess over mass-matched random **0.319**), byte- and
pixel-unique **[measured-here, incomplete corpus]**. Format: float32, EPSG:32611, 3730×3292, transform and bounds
identical to `sample_submission.tif`, 37,654 positive pixels, finite values in [0,1], **no NaN anywhere**, 0 dots
on the catalogue **[measured-here]**. No organizer-confirmed score exists for this file; none is projected.

## 3 · Answers to the two questions the brief asks

**Why did `h33-h33-2-b2` score 0.2778 (the family's best)?** Not because its field was good, but because its
*mass* was near-minimal on a well-ranked field: a five-rung pruning ladder (121,131 → 60,069 → 44,090 → 40,199 →
37,654 dots; 0.1922 → 0.2477 → 0.2600 → 0.2708 → 0.2778, all owner-reported) in which every deletion of dots
*raised* the score, and the two deletions that were measured removed dots sitting exactly 1 px and 2 px from the
published catalogue. Under the official metric `DTI = TP_w/(TP_w + 0.2·FP_w + 0.8·FN_w)` with a 300 m triangular
kernel, emitted mass costs `0.2·p(x)·(1−k)`, so a dot pays only if its kernel credit exceeds `0.2·DTI` ≈ 0.056.
The 0.2778 artifact has 0 dots on the catalogue, its nearest dot exactly 3.00 px (300 m) away, and a median dot
1.97 km from it: it is a wide-field emission whose merit is that it stops wasting mass where the answer is provably
not. Source for the algebra and the ladder: the official
[problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/) (metric + worked example
TP=3.00/FP=1.89/FN=2.00→0.60, read this session) and `60GEMSDOE/docs/research/why-02778-and-what-beats-it-2026-10-11.md`.

## 4 · Reproduce

```bash
python -m venv venv && . venv/bin/activate && pip install -r requirements.txt
bash scripts/download_competition_data.sh       # fetches & reassembles competition rasters + external stacks
python scripts/prepare_data.py                  # verifies SHA-256, CRS, shapes, band counts & generates manifest
python scripts/run_h66.py s0 s1 s2 s3 s4 s4b s5  # ~4 min, 3 GB RAM, no GPU
python scripts/verify66.py --candidate docs/downloads/<file>.tif
python scripts/write_run_card.py && python scripts/build_site.py && python scripts/build_site66.py
pytest tests/ -q                                # 70 passed
```

## 5 · Remaining work / limitations (owned, not deferred)

1. **Governance wall #1 (owner decision).** The registered holdout's truth *is* catalogue trace, so an emission that
   excludes everything within 300 m of the catalogue scores exactly 0.0 there — including a file that scored 0.2778
   live (measured: 0.004729 for the champion, 0.0 for ours). Any rule of the form "must beat the current holdout
   best before a slot" cannot promote off-catalogue work. Flag: `IR-66-GATE-01`.
2. **Governance wall #2 (inherited).** The literal "≤70 % of dots within 3 px of any registry raster" clause is
   unsatisfiable against space-filling comparators (60GEMSDOE measured 99.87 %). We report both the literal number
   (0.5099, passes) and the excess over mass-matched random (0.319, passes), plus the corpus coverage, instead of
   quietly redefining the rule.
3. **Native resolution is blocked by data, not by ideas.** Steger sub-pixel lines and a 2–20 m Frangi sweep on 1 m
   pixels cannot be run footprint-wide here. The fix is one GitHub-Actions bridge job (pattern already exists in
   `60GEMSDOE/.github/workflows/dem10-chi.yml`) that fetches the pinned 3DEP 1 m tiles listed by the competition
   DEM-links PDF, computes the lane's two feature sets at 1 m, and uploads a 100 m aggregate with its own manifest
   — then this lane's E1/E2 re-run on real native data. Flag: `IR-66-RES-01`.
4. **Untried this session (budget spent):** H66-4 pluvial-shoreline veto; E0 native check on the two committed 3 m
   pilot tiles (`src/gemsdoe48/scarp3m.py` vendored for it, hashes pinned in `data/pilot/dem3m/dem_pilot_receipt.json`);
   H66-5 geo-energy convergence.
5. **The 0.2778 anchor is owner-reported**: no organizer receipt links it to the exact bytes; every inversion of it
   inherits that caveat.

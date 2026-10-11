# GEMSDOE66 — an auditable fault-discovery system for the DOE GEMS Prize (DrivenData #306)

**Competition:** [DOE GEMS Prize](https://www.drivendata.org/competitions/306/competition-doe-gems/)
· **Problem description:** [page 967](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
· **Rules (PDF):** [docs.nlr.gov/docs/fy26osti/96647.pdf](https://docs.nlr.gov/docs/fy26osti/96647.pdf)
· **Live site:** <https://buffedlizard55-lab.github.io/GEMSDOE66/>
· **Lane (this session):** native-resolution lidar scarp channels — scarplet template
matching, Steger sub-pixel line extraction and Frangi multiscale Hessian line measures.

> ### Our Core Values — kept central to every decision in this repository
> **Maximize P(Win).** *"Maximize the Probability of Winning"* is our decision-making
> framework. In every decision we weigh tradeoffs, assess risk, and choose the path that
> maximizes the probability that we win this prize. We set aside our emotions and make tough
> decisions in order to maximize P(Win). It frees us from constraints and clarifies that we
> must put the outcome first.
>
> **Own the Outcome.** We own results end to end — not just our individual slice of the work.
> When problems arise and we have the means to act, we do so without waiting for permission or
> assignment. We treat failure and success as signals and use them to improve. We stay
> accountable to the final outcome.

---

## ⬇ SUBMISSION FILE — download, then upload to the submission page

**One file. Click the link, save the `.tif`, upload it.**

👉 **[`docs/downloads/gems66-<slug>.tif`](docs/downloads/)** — single-band `float32`
GeoTIFF, EPSG:32611, 3730 × 3292, 100 m, values in **[0, 1]**, NaN outside the footprint.

Exactly how to submit, and why the file is safe to upload, is on the
**[Executive summary](docs/executive-summary.html)** page. Short version:

1. Download the `.tif` from the [downloads](docs/downloads/) page (or the
   [zip](docs/downloads/) if your browser mangles GeoTIFFs).
2. Go to <https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/>.
3. **File to submit** → choose the downloaded `.tif`.
4. **Note (optional)** → paste the one-line comment given next to the file on the downloads
   page (it is already written for you and is under 140 characters).
5. **Create submission.**

It will pass the portal's `Predicted values must be in range [0, 1]` check: that check is
one of the twelve that `scripts/validate_submission.py` re-runs on the exact bytes before the
file is published.

---

## Status of this session

| gate | result |
|---|---|
| data restored from hash-pinned GitHub mirrors | **23/23 PASS** ([receipt](data/restore_receipt.json)) |
| official metric re-derived and unit-tested against a brute-force transcription | **PASS** (1e-9) |
| lane field computed | **PASS** |
| 8-fold blocked novelty holdout | see `evidence/experiment1_holdout.json` |
| duplicate / lane-drift gate vs 60 registry rasters | see `evidence/uniqueness_<slug>.json` |
| submission validator (12 checks) on the shipped bytes | see `docs/downloads/checks-<slug>.json` |

**Nothing in this repository carries an organiser score.** Every leaderboard number quoted
here is an owner report or a public-page snapshot and is labelled as one.

---

## 1. What the competition actually asks for

From the [problem page](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/):

> "we have consulted with fault experts who have **manually identified faults that are not
> contained within the current public USGS database**. These new faults will comprise the test
> dataset"

So the scored truth is **disjoint from the 60,988 labelled pixels** shipped as `labels.tif`.
Any model validated only against `labels.tif` is being graded on the wrong exam. This single
fact drives every design choice below.

### The metric, transcribed from the page

With `k(d) = max(1 - d/300 m, 0)`, `alpha = 0.2`, `beta = 0.8`:

```
TPw = sum_g  max_x  p(x) k(d(x,g))
FPw = sum_x  p(x) [1 - max_g k(d(x,g))]
FNw = sum_g [1 - max_x p(x) k(d(x,g))]
DTI = TPw / (TPw + 0.2 FPw + 0.8 FNw + eps)
```

Because `FNw = |G| - TPw` exactly, writing `T = TPw`, `S = sum p`, `M = sum p·max_g k`:

```
DTI = T / (0.2 T + 0.2 (S - M) + 0.8 |G|)
```

and the first-order condition for adding a unit of mass is

```
adding mass raises DTI  <=>  k > 0.2 * DTI        (a credit bar of 0.056 at DTI = 0.28)
```

**The metric is a budget, not a segmentation score.** Every emitted pixel costs `alpha = 0.2`
whether or not it earns credit. That is why the family's best rasters are sparse dot sets
(~38–46 k pixels out of 5.17 M) rather than dense probability maps.

## 2. Data

All competition bytes are login-walled at drivendata.org. The only reachable copy is the set
of **owner-supplied public GitHub blobs** pinned by sha256 in
[`registry/data_manifest.json`](registry/data_manifest.json).
They are **not organiser-authenticated**; the pin is what makes them usable.

```bash
python3 scripts/fetch_mirrors.py            # 23/23 PASS, ~420 MB, hash-verified
python3 -m gemsdoe66.features               # 59-layer footprint stack -> data/processed/
```

| group | layers | source |
|---|---|---|
| competition bands (19) | magnetics, gravity, geodetic strain, seismicity, MT, topography | organiser, via mirror |
| **1 m LiDAR scarp descriptors (12)** | `ex_max, ex_mean, step_max, lapneg_max, lappos_max, downface_max, upface_max, cross_max, relief, coh100, strike, valid` | owner CI from [USGS 3DEP 1 m DEM](https://www.usgs.gov/3d-elevation-program) (706/716 tiles) |
| 10 m DEM topography (9) | slope/relief/curvature/aspect-coherence/hillshade-lineament | owner CI from USGS 3DEP 10 m |
| channel steepness χ (6) | `chi_b1..5, chi_sig` — **25 of 36 blocks succeeded** | owner CI from USGS 3DEP 10 m |
| GeoDAWN radiometrics (8) | K, Th, U, TC, Th/K, U/K, U/Th, TMI↑150 m | [GeoDAWN](https://www.sciencebase.gov/catalog/item/657e1d85d34e23d3533209f7), DOI 10.5066/P93LGLVQ |
| independent inventories (5) | SGMC faults, GDR QFaults v2, paleo, volcanic vents | [USGS SGMC](https://mrdata.usgs.gov/geology/state/), [GDR 1391](https://gdr.openei.org/submissions/1391) (CC BY 4.0) |

## 3. The method in one page

1. **Footprint + grid** are read from `sample_submission.tif` and asserted, never assumed.
2. **Feature stack**: 59 layers, dequantised back to physical units, stored as one on-disk
   `float32` memmap of footprint pixels (`src/gemsdoe66/features.py`).
3. **Fields** (`src/gemsdoe66/fields.py`) — a field is a full-grid belief surface:
   * `lidar_lane` — the assigned lane: Frangi multiscale vesselness, Steger sub-pixel line
     localisation and structure-tensor orientation coherence/dominant strike at 2–20 pixel
     (200–2000 m) scales on the slope-detrended surface, fused with the 1 m-LiDAR scarp
     amplitude × coherence and a strike-concordance term, masked against flat/high-slope
     cultural ground.
   * `catalogue_habitat` — gradient boosting on the given catalogue (the control that
     represents what the existing family implicitly does).
   * `sgmc_novel` — gradient boosting on **SGMC faults > 300 m from the given catalogue**
     (61,664 px): the only large inventory of real faults the given catalogue lacks.
4. **Holdout** (`src/gemsdoe66/holdout.py`) — two instruments, 8 spatially coherent balanced
   folds by connected component, 300 m buffer removed from **training only**:
   * **N (primary)**: truth = SGMC off-catalogue faults.
   * **C (control)**: truth = withheld components of the given catalogue.
5. **Emission** (`src/gemsdoe66/emission.py`) — greedy packing at a fixed budget with a
   minimum separation, deleting every dot within 200 m of the known catalogue.
6. **Submission** (`src/gemsdoe66/submission.py`) + **validator**
   (`src/gemsdoe66/validate_submission.py`) + **duplicate gate**
   (`src/gemsdoe66/uniqueness.py`).

## 4. Irregularities logged this session

| id | what | status |
|---|---|---|
| **IR-66-SCORE-01** | The task brief states "0.3195 is the highest score right now". The live public leaderboard on 2026-10-11 shows **0.4133 at #1**; 0.3195 (DARD) is now **rank 9**. The brief's number is a stale snapshot. | open — the target is re-stated as 0.4133 |
| **IR-66-DATA-01** | The sandbox has outbound access to **github.com, api.github.com, pypi.org and their CDNs only**. `prd-tnm.s3.amazonaws.com`, `earthquake.usgs.gov`, `gdr.openei.org`, `sciencebase.gov` and `dropbox.com` all return HTTP 000. Raw 1 m GeoDAWN lidar and 10 m 3DEP tiles are therefore **not obtainable here**. | open — lane executed on the pinned 1 m-derived 100 m aggregate |
| **IR-66-DATA-02** | The 10 m-DEM χ product covers only **25 of 36 blocks** (`dem10_chi_100m.manifest.json`). | noted; χ used with its coverage mask |
| **IR-66-PROXY-01** | A layer's dot-mean correlates with the owner-reported live score at up to \|ρ\| = 0.98, but **also** with the number of emitted dots at \|ρ\| = 0.5–0.9. The five lidar scarp channels flip sign under nuisance control, so their apparent live signal is an artifact of dot count. | open — see §6 |
| **IR-66-BUG-01** | The first holdout run excluded the held-out truth's 300 m buffer from *emission* as well as training, forcing TPw = 0 for every candidate. Fixed; the buffer is training-only. | fixed |

## 5. Reproduce

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
python3 scripts/fetch_mirrors.py                 # 23/23 hash-verified
python3 -m gemsdoe66.features                    # build the 59-layer stack
python3 -m gemsdoe66.fields                      # compute the lane field
python3 scripts/run_experiments.py               # 8-fold blocked holdout
python3 scripts/build_submission.py              # emit + write the GeoTIFF
python3 scripts/check_submission.py              # 12 portal checks + duplicate gate
.venv/bin/python -m pytest tests -q
```

## 6. What we learned about scoring higher

Measured, not asserted. Full numbers in `evidence/`.

* **The emission envelope is a solved problem.** Every raster in the family that scores
  ≥ 0.2376 has the same shape: 37–46 k binary dots, minimum separation ≈ 2.83 px, and
  **zero dots within 200 m of the known catalogue**. Deleting the 2,545 dots of the 0.2708
  raster that sat within 200 m of the catalogue is what produced 0.2778.
* **Everything above that is field quality.** Two rasters with the same envelope and the same
  dot count score 0.2376 and 0.2778 — a 0.04 spread that is entirely *where* the dots are.
* **Solving `DTI = T/(0.2S + 0.8G)` for the 0.2778 → 0.2708 pruning pair gives
  |hidden truth| ≈ 15,000 px** and captured weighted credit T ≈ 5,470 (weighted recall
  ≈ 36 %). At that truth size a *perfect* field at the same 37,654-dot budget scores 0.77.
  The gap between 0.28 and 0.77 is detector quality, and it is the whole prize.
* **A proxy whose truth is the given catalogue cannot reward a new fault**, and the family
  has measured this before (IR-32-PROXY-01). We therefore use the SGMC off-catalogue
  population as the primary holdout truth.
* **The five H33 hypotheses (multi-physics orientation consensus, aligned drainage chains,
  en-echelon scarplet chains, straight conductivity boundaries, …) were already tried in
  GEMSDOE32 and none promoted.** Anything built here must differ from those.

## 7. Limitations

1. **No raw 1 m lidar and no 10 m DEM** (IR-66-DATA-01). The scarplet template matching of
   Sare & Hilley (JOSS 2018, [doi:10.21105/joss.01066](https://doi.org/10.21105/joss.01066))
   cannot be re-run on native-resolution data here; the lane is executed on the pinned
   1 m-derived 100 m descriptor stack and on the 100 m detrended elevation.
2. **No GPU, 2 CPUs, 3 GB RAM.** Model capacity is deliberately small.
3. **No organiser score exists for any artifact here**, and no hash-to-score crosswalk is
   public, so owner-reported scores are used as the only live anchor — with n ≈ 18 and heavy
   collinearity, they are a prior, not evidence.
4. **Only 3 scored submissions per week** may be spent, and the same file is scored in both
   prize rounds.

## 8. Repository layout

```
scripts/     fetch_mirrors, build stack, experiments, build/check submission, docs build
src/gemsdoe66/  grid, metric, features, fields, emission, holdout, submission,
                validate_submission, uniqueness
registry/    data_manifest.json (23 hash-pinned mirrors); rasters/ (60 prior submissions)
evidence/    every measurement this repo makes, as JSON
docs/        GitHub Pages site: index, executive summary, hypotheses, research, sources
```

---

## Appendix A — the project brief (kept here as the standing starting point)

> Review the repo. THE FOLLOWING IS THE HIGHEST URGENCY AND MUST BE FOLLOWED! MUST GENERATE A
> UNIQUE TIF SUBMISSION FOR THE COMPETITION. DO NOT COPY A PREVIOUS SUBMISSION UNLESS IT'S
> FOR LEARNING AND EDUCATION. BUT WE MUST GENERATE A UNIQUE TIF SUBMISSION. IT MUST BE OBVIOUS
> WHETHER IT IS OK TO DOWNLOAD AND SUBMIT THE GENERATED TIF SUBMISSION.
>
> Native-resolution lidar scarp channels. The 100 m stack discards the subtle scarps visible
> in the 1 m GeoDAWN lidar, which plausibly is evidence geologists use to add faults. On
> high-prior tiles first, compute two sets of features. (i) scarplet template matching
> (Sare & Hilley, JOSS 2018, doi:10.21105/joss.01066), which returns amplitude, relative age,
> orientation and SNR from a GeoTIFF DEM, extended with slope-aware scarp templates (AGU 2015
> poster T31A-2838, tested in Surprise Valley). (ii) Steger sub-pixel ridge/valley lines
> (IEEE TPAMI 20(2):113–125, 1998) and Frangi multiscale Hessian line measures (MICCAI 1998,
> LNCS 1496:130–137) at 2–20 m scales on a slope-detrended surface. Aggregate to 100 m cells
> as scarp-pixel fraction, SNR-weighted amplitude, structure-tensor orientation coherence and
> dominant strike. Mask roads, canals and field edges with the existing cultural-feature mask,
> then retrain under spatial CV. Gate: DTI gain on lidar-covered holdout blocks that is not
> confined to range fronts. Finish: normalize to [0,1]; write a float32 EPSG:32611 100 m
> GeoTIFF (NaN only outside the footprint); pass `validate_submission.py`; run a hash/pixel
> agreement check against all prior rasters; offer the download only if the gate is met, else
> log the negative result.
>
> **PARALLEL-RUN PROTOCOL.** 1. LANE. Stay inside it. If your raster's rank-correlation with
> any registry raster exceeds 0.90, or more than 70 % of your dots fall within 3 px of one
> registry raster's dots, you have drifted into another lane: log it as a duplicate and stop.
> Check on the surface before placement AND on the final dots. 2. REUSE, DON'T REBUILD. Use
> the template's cached feature stack, `evaluate_holdout.py` and `submission_writer.py`.
> Holdout = hide-and-recover: withhold whole fault segments with a buffer, derive every
> catalogue-based feature only from the visible faults, mask visible faults pixel-exactly,
> score pooled DTI (alpha 0.2, beta 0.8, 300 m triangular kernel). If a shared tool is wrong,
> fix it once in the template and report it. 3. LABEL EVERY NUMBER as HOLDOUT-DTI (evaluator
> version, number of withheld positives, 95 % CI) or ORGANIZER-CONFIRMED (copied from a
> submission-page receipt). A projection is never written as a score. 4. LEAKAGE CANARY. Test
> each feature alone on the holdout before trusting any result. AUC above 0.90 means leakage
> until proven otherwise. 5. RUN CARD. End with one JSON card. 6. BUDGET. Stop after 3
> experiments or 2 hours. Do not pick submissions; promotion to a real slot is a separate
> selector step, within the weekly cap shown on the submission page.
>
> Site requirements: a GitHub Pages site with clean UI; the download must be obvious at the
> top; an executive-summary subpage explaining exactly how to submit; unique name and a short
> comment (≤ 140 characters) for the submission form; fix the
> `Predicted values must be in range [0, 1]` rejection.
>
> Work line by line, verify from official trusted sources, provide links for manual review.
> No hallucinations. Flag any irregularities for review.

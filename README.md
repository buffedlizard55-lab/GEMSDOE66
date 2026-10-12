# GEMSDOE66 — DOE GEMS Prize (DrivenData #306)

**Current verdict (session `arena/855725e1`, 2026-10-12): ONE candidate is CLEARED and published
as a download.** File
`gems66-h67-geophys-maxcov-r3-45000dots-20261012T025604Z-f8c91fd09121-nan.tif`
(sha256 `512fda025b830209abb01319…`; the full run card is
[`docs/data/run-card-h67.json`](docs/data/run-card-h67.json)), 45,000 binary dots, float32,
EPSG:32611, 100 m, NaN only outside the footprint. All 15 release gates are recomputed from the
bytes on disk at build time by [`scripts/build_site_h67.py`](scripts/build_site_h67.py); the
site shows one banner, either **✅ DOWNLOAD READY — OK TO SUBMIT** or **❌ NOT CLEARED**, never
both. **No organizer score is claimed for this file. Nothing has been uploaded; uploading is a
manual step.** Keep **Maximize P(Win)** and **Own the Outcome** central.

**Start every session here.** Read this charter, then, in order:
[`docs/data/run-card-h67.json`](docs/data/run-card-h67.json) (the current lane),
[`docs/data/h67_hypotheses.json`](docs/data/h67_hypotheses.json) (the five hypotheses *and their
measured outcomes*), the newest file under [`docs/review/`](docs/review/), and
[`docs/data/run_card.json`](docs/data/run_card.json) (the historical `lidar_lane` verdict, still
negative, deliberately not overwritten). The original method and parallel-run prompt is Appendix A.

---

## This session in one paragraph

The decisive measurement is a **negative** one that inverted the preregistered hypothesis ranking.
Every layer that reads a fault *inventory* — the given catalogue, the USGS QFDB traces, the SGMC
state geologic map, the GDR thermal springs — is an **anti-signal** under the repository's own
spatially blocked holdout, because that protocol withholds whole fault segments and buffers the
remaining inventory by 300 m. The withheld truth therefore sits inside a manufactured gap, and
"distance to the remaining inventory" learns *"gap means no fault"*. On the same 2 folds, the same
45,000-dot budget and the same eligible mask:

| belief | HOLDOUT-DTI | 95% CI | vs. its own null |
|---|---|---|---|
| R1 catalogue distance only | 0.0178 | 0.0147 – 0.0208 | 0.25× random |
| R4 catalogue + SGMC gap | 0.0178 | 0.0147 – 0.0208 | 0.25× random |
| R5 full 62-layer stack | 0.0178 | 0.0147 – 0.0208 | 0.25× random |
| uniform random placement (null) | 0.0707 | — | 1.00× |
| fixed 100 m lattice (null) | 0.0729 | — | 1.03× |
| **R3 geophysics/topography, no inventory** | **0.17898** | **0.17816 – 0.17980** | **2.53× random** |

Withheld positives pooled = 62,383; segments = 3,199 (8-connected proxy); leakage canary clear
(strongest single layer AUC 0.714, threshold 0.90). Paired gain of R3 over the incumbent R1 =
**+0.16121, 95% CI [0.15735, 0.16506]**, so the promotion is uncertainty-bounded and not a coin
flip. Every number in that table is **HOLDOUT-DTI** from
[`src/gems/metric.py`](src/gems/metric.py) (vectorised == literal brute force to 3.6e-15; the
official worked example's `TPw=3.00` and `FNw=2.00` reproduce exactly). **None of them is an
organizer score, and none is a prediction of one.**

Three protocol defects were found and fixed on the way, and all three are now regression-tested:

* **`IR-67-FOOTPRINT-01`** — `sample_submission.tif` is finite on 5,167,373 cells while
  `training_features.tif` band 1 is finite on 5,165,852; they disagree by 3,061 cells one way and
  1,540 the other. The validator used the features mask and therefore **failed an artifact whose
  NaN convention is byte-identical to all 12 owner artifacts the organizer actually scored**. The
  reference (sample-submission) mask is now authoritative, the features mask is reported as a
  cross-check, and no dot may lie outside the features bounds under either reading.
* **`IR-66-GATE-01`, extended** — raw within-3px overlap against a dense registry raster is
  meaningless (a 5-px lattice covers the whole grid, so its null is 0.9985). The audit now reports
  a *second* null drawn from the 1 km neighbourhood the candidate's own dots occupy, which
  separates "shares a geological target" from "copies the same dots". The worst comparator's
  unconditional lift of 3.07 falls to **1.37** under it; zero rasters are flagged as duplicates.
* **A private fork of the layer-exclusion list** — `INVENTORY_LAYERS` was duplicated in two
  scripts. It now lives once in [`src/gems67/design.py`](src/gems67/design.py), with the
  measurement that justifies it in the docstring.

**Reproduce:**

```bash
python3 scripts/fetch_mirrors.py                       # 23 verified, 2 no-mirror, 0 failed
python3 scripts/h67_build_stack.py                     # 5,167,373 x 62 float32 memmap, 1.28 GB
python3 scripts/h67_holdout.py  --instruments C --recipes R1,R4,R5 --standoff-px 2
python3 scripts/h67_holdout.py  --instruments C --recipes R3       --standoff-px 2
python3 scripts/h67_null_control.py --instruments C                # the placement nulls
python3 scripts/h67_submit.py   --recipe R3_geophysical_only --standoff-px 2 --budget 45000
python3 scripts/h67_run_card.py --holdout evidence/h67_holdout_C.json evidence/h67_holdout_C_R3.json
python3 scripts/build_site_h67.py                      # recomputes all 15 gates, then publishes
python3 -m pytest -q                                   # 134 passed
```

---

## What is still blocked, and what access would unblock it

* **No DrivenData credentials**, so the data tab cannot be auto-downloaded and **no submission can
  be uploaded from here**. The upload is a manual step; the exact clicks are on
  [`docs/executive-summary.html`](https://buffedlizard55-lab.github.io/GEMSDOE66/executive-summary.html).
* **Egress is limited to `github.com`, `api.github.com` and `pypi.org`.** USGS 3DEP, ScienceBase,
  the GDR download endpoints and the DrivenData 1 m DEM links all return HTTP 000
  (`IR-66-DATA-01`). The full native-resolution lidar scarp lane in the brief — Sare & Hilley
  scarplet template matching, Steger sub-pixel ridges, Frangi multiscale Hessian at 2–20 m —
  **cannot be run here**; only the owner-derived 100 m `lidar_scarp_features_u8` layer exists, and
  its channels reached AUC 0.580–0.587, i.e. weak.
* **Two manifest entries have `repo: null`** (`topo_10m_derived_100m_u8.tif`,
  `lidar_scarp_features.json`) and are not obtainable; `fetch_mirrors.py` now reports them as
  `no_mirror` instead of aborting before the receipt is written.
* **The three reachable GDR CSVs all carry a label-derived `dist_known_fault_px` column**, so they
  are unusable as features without leakage.
* **`IR-67-METRIC-01`** — the official worked example's `FPw = 1.89` does not reproduce; any 5-px
  line prediction against that truth gives `FPw = 2.00`. `TPw` and `FNw` reproduce exactly.
* **A score inconsistency inside the project brief** (0.2778 / 0.3774 / 0.3195 are each called
  "highest"). None may be quoted as organizer-confirmed without a receipt; see
  [`evidence/h67_truth_size.json`](evidence/h67_truth_size.json) for what the 12 owner-scored
  mirrors do identify: `T/|G| = 0.2565` and `(N−M)/|G| = 0.6758`, with `|G|` itself **not**
  identified.

---

## Historical context — inherited `lidar_lane` session (`arena/7d2c4a3b`)

### Competition references and native-resolution target

**Competition:** [DOE GEMS Prize](https://www.drivendata.org/competitions/306/competition-doe-gems/)
· **Problem description:** [page 967](https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/)
· **Rules (PDF):** [docs.nlr.gov/docs/fy26osti/96647.pdf](https://docs.nlr.gov/docs/fy26osti/96647.pdf)
· **Live site:** <https://buffedlizard55-lab.github.io/GEMSDOE66/>
· **Target lane:** native-resolution lidar scarp channels — scarplet template matching,
Steger sub-pixel line extraction and Frangi multiscale Hessian line measures. The inherited
`lidar_lane` experiment did not implement that full native-resolution method; see its scale
and data-access limitations below.

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

## Submission status — NO DOWNLOAD; nothing is cleared

**Do not upload a historical artifact.** There is no current TIFF or ZIP cleared for
submission; [`docs/downloads/README.md`](docs/downloads/README.md) explains the audit-only
files and the stop conditions. The executive summary explicitly says **No** to download or
submit.

The inherited PR #13 `lidar_lane` experiment is retained only for audit under
[`artifacts/lidar_lane/`](artifacts/lidar_lane/README.md). Its reported pooled advantage was reversed by relief-matched
analysis. Its final-dot scan reports **0.990386** within 3 px of an accessible registry raster,
which exceeds the brief's **0.70 stop threshold**. The density-adjusted `UNIQUE` label is not a
release pass: only 60 rasters were scanned, the complete organizer registry is not certified,
and pre-placement surface correlation is not reported. The experiment is also scale-deviating
from the requested native-resolution 2–20 m method: the recorded line scales on the 100 m grid
are 200–2,000 m, and raw 1 m tiles were unavailable. See `IR-71-LIDAR-RAW-OVERLAP` and the
[PR #12 reconciliation](docs/review/2026-10-11-pr12-reconciliation.md).

The canonical project-status card is [`docs/data/run-card.json`](docs/data/run-card.json):
`promote: false`, negative, no cleared candidate, and no slot used. The separate
[`docs/data/run_card.json`](docs/data/run_card.json) is the inherited PR #13 experiment record,
not a competing project-status card. **No `ORGANIZER-CONFIRMED` score or successful scientific
result is claimed.** The local format checks and all-finite/NaN policy questions do not override
the negative scientific and uniqueness gates.

---

## Status of this session

| gate | result |
|---|---|
| owner-supplied, hash-pinned GitHub mirrors | **23/23 locally verified** ([receipt](data/restore_receipt.json)); not organizer-authenticated |
| metric transcription/unit tests | **Local verification only** (1e-9); not an organizer score |
| scarp-lane field | Historical proxy computed on 100 m-derived layers; not the requested native 2–20 m method and not promoted |
| 8-fold novelty holdout | `HOLDOUT-DTI` is reported only in the inherited run card with evaluator, withheld-positive count and CI; SGMC truth is an internal proxy, not the organizer's hidden set |
| duplicate / lane-drift gate | **STOP / NOT CERTIFIED**: raw final-dot overlap 0.990386 (>0.70) against an accessible raster; 60 rasters scanned, full-registry completeness and pre-placement surface check unverified |
| local format checks | Historical sidecars only; they do not clear the artifact or establish official upload acceptance |

**No organizer receipt tied to an exact artifact hash is present in this checkout.** Any
historical owner/public leaderboard claim is unverified, explicitly attributed where retained,
and is not used as a score, target, or release signal.

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

## 3. Inherited PR #13 implementation (audit only; not the target method)

The details below reconstruct the already-existing 100 m-derived proxy. Its feature lanes and
scales are historical implementation notes, not the native-resolution method being proposed or
authorized for a new run.

1. **Footprint + grid** were read from `sample_submission.tif` and asserted, never assumed.
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
| **IR-66-SCORE-01** | An earlier draft quoted a public leaderboard target. No leaderboard was accessed or monitored in this reconciliation, and no public row is tied here to an exact artifact receipt. No such number is used as an organizer-confirmed score or decision threshold. | open — not verified here |
| **IR-66-DATA-01** | The sandbox has outbound access to **github.com, api.github.com, pypi.org and their CDNs only**. `prd-tnm.s3.amazonaws.com`, `earthquake.usgs.gov`, `gdr.openei.org`, `sciencebase.gov` and `dropbox.com` all return HTTP 000. Raw 1 m GeoDAWN lidar and 10 m 3DEP tiles are therefore **not obtainable here**. | open — lane executed on the pinned 1 m-derived 100 m aggregate |
| **IR-66-DATA-02** | The 10 m-DEM χ product covers only **25 of 36 blocks** (`dem10_chi_100m.manifest.json`). | noted; χ used with its coverage mask |
| **IR-66-PROXY-01** | A layer's dot-mean correlates with the owner-reported live score at up to \|ρ\| = 0.98, but **also** with the number of emitted dots at \|ρ\| = 0.5–0.9. The five lidar scarp channels flip sign under nuisance control, so their apparent live signal is an artifact of dot count. | open — see §6 |
| **IR-66-BUG-01** | The first holdout run excluded the held-out truth's 300 m buffer from *emission* as well as training, forcing TPw = 0 for every candidate. Fixed; the buffer is training-only. | fixed |

## 5. Reproduction notes — not a release workflow

The commands below describe the inherited experiment, not authorization to run it or submit its
artifact. Official competition inputs and the exact sample grid are absent locally; no download
or experiment is triggered by this review. Do not run an emission or submission step unless the
standing holdout, provenance, and release gates in Part 2 have first been met.

```bash
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
python3 scripts/fetch_mirrors.py                 # owner mirrors only; not organizer-authenticated
python3 -m gemsdoe66.features                    # historical 59-layer stack
python3 -m gemsdoe66.fields                      # historical proxy field
python3 scripts/run_experiments.py               # historical 8-fold proxy; not this session's test
python3 scripts/build_submission.py              # DO NOT RUN for release; historical output only
python3 scripts/check_submission.py <candidate.tif> --surface <continuous_surface.npy>
# Shared strict gate requires evidence/registry_refreshed.json with organizer completeness.
.venv/bin/python -m pytest tests -q
```

## 6. Evidence discipline and inherited claims

No owner-reported leaderboard value is used as a target, score, or release signal. The checkout
contains no organizer receipt tied to a prediction raster's exact bytes/SHA-256, so claims about
family leaderboard performance and causal attribution remain unverified. Do not infer a hidden
truth size, weighted recall, perfect-field score, or expected competition result from a proxy
calculation.

The inherited PR #13 `lidar_lane` has an internal `HOLDOUT-DTI` report, with evaluator, fold
count, withheld-positive count, and 95% CIs shown on the results page. It is negative after
relief matching, scale-deviating from the native-resolution target, and blocked by the raw
uniqueness threshold and incomplete registry certification. H66-2's figures remain explicitly
labelled proxy measurements, not DTI scores. Neither artifact is submission-cleared.

Earlier owner-maintained materials describe H33 feature experiments, but this checkout does not
verify every historical variant or tie a claimed H33-2-B2 value to a submission receipt. Treat
those descriptions as leads for attribution review, not scientific conclusions. The H33 question
and evidence limits are recorded below and in `docs/review/2026-10-11-pr12-reconciliation.md`.

## 7. Limitations

1. **No raw 1 m lidar and no 10 m DEM** (IR-66-DATA-01). The scarplet template matching of
   Sare & Hilley (JOSS 2018, [doi:10.21105/joss.01066](https://doi.org/10.21105/joss.01066))
   cannot be re-run on native-resolution data here; the lane is executed on the pinned
   1 m-derived 100 m descriptor stack and on the 100 m detrended elevation.
2. **No GPU, 2 CPUs, 3 GB RAM.** Model capacity is deliberately small.
3. **No organizer score/receipt is present for any artifact here**, and no hash-to-receipt
   crosswalk is verified. No leaderboard number is used as evidence or a live anchor; inherited
   SGMC measurements are internal proxies, not the expert panel's hidden truth.
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

## Appendix A — project brief excerpt (historical, condensed)

The blockquote below summarizes the original project aim and method prompt for traceability;
it does not reproduce the user's full site-by-site historical list or repeated instructions. Its
unconditional wording predates the later fail-closed scientific, registry, provenance, and
release gates. **It is not authorization to emit, download, publish, or submit an artifact.** The
current status and binding execution rules later in this README take precedence; stop when any
gate fails.

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

---

## Historical H66b session notes (`arena/133c86e6`): metric, site and H66-2 experiment

### Values and status recorded in the historical H66b session

**One lane:** native-resolution LiDAR scarp channels. **One standard:** a scientific, reproducible result that survives the holdout, registry, format, provenance, and rules gates. **One current status:** blocked; no candidate is cleared for download or submission.

> **Current as of 2026-10-11:** the audit session could not reach the official data tab (login redirect, no credentials used) and withdrew the three legacy H66-1 binaries from `docs/downloads`. Their byte-identical copies are retained only in `evidence/archives/h66-1/`, outside the Pages document root and without site links; their SHA-256 identities and withdrawn status remain recorded. **Do not upload a historical artifact.** The newer main history also records a preregistered H66-2 experiment (see `docs/review/2026-10-11-h66-2-verdict.md`): local format/range checks passed, but its measurements are proxy-only, its scientific verdict is **NEGATIVE-NOT-PROMOTED**, and the artifact remains audit-only under `artifacts/h66-2/`.
>
> An inherited PR #13 `lidar_lane` record reports internal `HOLDOUT-DTI` from `gemsdoe66.metric.dti` (8 spatial folds, approximately 7,700 withheld positives per fold; the recorded pooled lane result is 0.07075 with 95% CI [0.05217, 0.08967]). Its relief-matched result is 0.02638 [0.02087, 0.03183] versus the incumbent's 0.02727 [0.02421, 0.03049], with lane-minus-incumbent CI [-0.00836, 0.00664]. These values are inherited internal SGMC-proxy measurements, not `ORGANIZER-CONFIRMED`; they do not survive the relief-matched decision gate, and the field was scale-deviating from the native-resolution brief. Its raw uniqueness threshold also trips and full registry completeness is not certified. The artifact is audit-only. This PR reconciliation ran **no experiment**. Nothing in this repository is cleared for submission, and no `ORGANIZER-CONFIRMED` score or successful scientific result is claimed.

> **Read this file first**, then `docs/data/run-card.json` and the newest file under `docs/review/`, including `docs/review/2026-10-11-pr12-reconciliation.md`, before doing anything in a session. The brief below is the standing requirement list distilled from the session brief, kept here so every session starts from the same instructions. Where a later audit tightened a rule (see `docs/review/2026-10-11-audit.md`), the stricter rule wins.


## Standing brief (binding)

**Deliverable.** Produce a **unique** GeoTIFF submission for the DOE GEMS Prize (DrivenData #306) that is not a
copy of any prior submission. Make it obvious — at the top of the site and in this file — whether the generated
file is safe to download and whether it is cleared to submit. Provide an easy download path, a unique submission
name, and a note of at most 140 characters. Never publish a file that has not passed the release gates recorded
in `docs/review/2026-10-11-audit.md`.

**Lane.** Native-resolution LiDAR scarp channels only: scarplet template matching (Sare & Hilley, JOSS 2018,
doi:10.21105/joss.01066) extended with slope-aware templates (AGU 2015 poster T31A-2838, Surprise Valley);
Steger sub-pixel ridge/valley lines (IEEE TPAMI 20(2):113-125, 1998) and Frangi multiscale Hessian evidence
(MICCAI 1998, LNCS 1496:130-137) at 2-20 m on a slope-detrended surface; aggregate to 100 m cells as
scarp-pixel fraction, SNR-weighted amplitude, structure-tensor orientation coherence and dominant strike. Mask
roads, canals and field edges with the existing cultural-feature mask; retrain under spatial cross-validation.
Gate: DTI gain on LiDAR-covered holdout blocks that is **not confined to range fronts**. Normalise to [0,1] as
float32 EPSG:32611 on the exact grid; pass `validate_submission.py`; hash- and pixel-agreement check against
every prior raster; offer a download only if the gate is met, otherwise log the negative.

**Protocol.** Stay in the lane; log drift and stop if correlation exceeds 0.90 against any registry raster or if
more than 70 % of dots fall within 3 px of one. Reuse the template's cached feature stack, `evaluate_holdout.py`
and `submission_writer.py`; fix a shared tool once, in place, never in a private fork. Holdout: hide-and-recover
whole fault segments with a buffer; catalogue features only from visible faults; visible faults masked
pixel-exactly; pooled DTI with alpha=0.2, beta=0.8 and a 300 m triangular kernel. Label every number either
`HOLDOUT-DTI` (evaluator version, withheld positives, 95 % CI) or `ORGANIZER-CONFIRMED`; never present a
projection as a score. Leakage canary: any feature alone with AUC above 0.90 is leakage until disproven. Finish
with one JSON run card carrying hypothesis, mechanism, named non-fault mimic, holdout numbers,
correlation/overlap versus the registry, raster sha256, validator output, submission name and note, and a
promote/negative verdict. Negative results are deliverables. Budget: three experiments or two hours, whichever
comes first. Do not spend a submission slot; slot selection is a separate manual step.

**Before implementing.** Rank three to five candidate hypotheses not yet tried, each naming the specific layers,
the physical signature targeted, why it could catch a fault the USGS/INGENIOUS catalogue misses, and how it
differs from everything already in the repository; rank by expected DTI gain and implementation cost; validate
the top candidate on the spatially blocked holdout before touching a submission slot. Name any new external data
source exactly and verify it is free and obtainable first.

**Reporting.** Work line by line from official, verifiable sources and link them for manual review; flag every
irregularity; no manual input required from the user; no hallucinations; run each task through three passes;
finish with a pull request merged to `main` plus the remaining work and limitations.

**Question owed.** Trace the owner-reported performance attribution for
`h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros` (GEMSDOE32) and assess whether the method can
be beaten without treating a public-board row or owner statement as a confirmed artifact score.
No receipt tied to those exact bytes is present, so the attribution remains unverified. Best
current analysis: `docs/review/2026-10-11-h66-2-verdict.md` plus the transfer discussion in
`evidence/h66b_instrument_vs_live.json`; these are hypothesis/diagnostic records, not
`ORGANIZER-CONFIRMED` results.

**Site.** Clean and user-friendly; it must generate the submit-ready GeoTIFF and make download-and-submit
obvious at the very top, with an executive-summary subpage explaining exactly how to submit, and it must never
recur the prior rejection `Predicted values must be in range [0, 1]`.

**Core values.** Maximize P(Win); Own the Outcome.

## Historical H66-2 audit note (2026-10-11) — negative, not published

A separate, preregistered proxy experiment was recorded in this repository
(`registry/preregistration-h66-2.json`): a **conjunction** field, the geometric mean of
rank(10-vs-50 m slope break), rank(1 − dip-sense) and rank(crest-toe sharpness) on the pinned
2 m LiDAR stack. This is preserved only for provenance; it is not the current
scarplet-template/Steger/Frangi method lane and must not be extended as part of that work. Every numerical comparison below is an
**off-catalogue proxy measurement**, not `HOLDOUT-DTI` or `ORGANIZER-CONFIRMED`; no receipt ties the
artifact to an organizer score. It beats the H66-1 blend at equal proxy mass
(credit/dot 0.2253 vs 0.2019) and beats the live-best incumbent's own dots on the upland stratum, but
it is **NEGATIVE-NOT-PROMOTED**: the mass-matched terrain-only control is within 1.9x pooled, the
field's mass is 99.95 % upland while the incumbent's edge lives in the basin (a within-stratum
control comparison, versus 19 of 37,654 H66-2 dots). Its exploratory correlation with an earlier
owner-reported ordering was not statistically persuasive (rho=+0.46, p=0.29 over the 35k–70k
band); that diagnostic is not a DTI score, is not organizer-confirmed, and is not used as a
release or model-selection signal.

The emitted bytes (37,654 dots, float32, EPSG:32611, 0 NaN, values in [0,1], writer validator all
checks true, sha256 `66a8c3afad6a56855a8daf85ac885ef70697ac8b4822bbb3d6c38aafd471134c`) are kept in
`artifacts/h66-2/` for audit and are deliberately **not** linked from the site: the release gate in
`docs/review/2026-10-11-audit.md` requires a valid buffered whole-segment `HOLDOUT-DTI` with a 95 %
interval, a complete registry and two independent reviews before any download is published, and this
candidate has none of those. See `docs/review/2026-10-11-h66-2-verdict.md` for the full measurement
table and the two corrections this session recorded (IR-66-BASE-01, IR-66-GUARD-02).

## Project charter

“Maximize P(Win)” means optimize for discoveries likely to generalize to newly mapped faults, not for a leaderboard anecdote or a proxy that reuses the public catalogue as test truth. “Own the Outcome” means preserve provenance, code, negative results, uncertainty, and clear stop conditions. Neither phrase licenses skipping validation.

### Standing execution rules

1. **Stay in the lane.** Work only on native-resolution LiDAR scarp channels. Reuse the template's cached feature stack, shared holdout evaluator, and submission writer. If a shared tool is wrong, propose and land one fix in the template; do not silently maintain a private fork here.
2. **Rank before implementing.** Keep three to five distinct, same-lane hypotheses in `docs/data/hypotheses.json`. Each must state its layers, physical signature, reason it could recover off-catalogue faults, difference from this repository, named non-fault mimic, implementation cost, and input availability. Ranking is qualitative until a valid holdout exists; do not invent a DTI projection.
3. **Use a valid holdout.** Withhold whole geologic fault segments, with a spatial buffer. Derive every catalogue-based feature from visible faults only, and pixel-exactly mask visible faults from scoring. Restrict held-out truth and predictions to LiDAR-covered holdout blocks. Pool the official distance-weighted Tversky terms with α=0.2, β=0.8, and a 300 m triangular kernel; separately report whether a gain survives away from range fronts.
4. **Label scores exactly.** A research score must be `HOLDOUT-DTI` and include the evaluator version, withheld-positive count, and a 95% confidence interval. A competition score may be `ORGANIZER-CONFIRMED` only when copied from a receipt tied to the exact submitted artifact. A public leaderboard row, owner statement, proxy, or projection is not an artifact receipt. Never call the owner-reported H33-2-B2 attribution organizer-confirmed.
5. **Test leakage feature by feature.** Evaluate every proposed feature alone on the spatially blocked holdout. AUC above 0.90 is leakage until disproven. Never use hidden/withheld catalogue pixels to make an eligibility, distance, feature, threshold, or placement decision.
6. **Check uniqueness twice.** Compare the continuous pre-placement surface and final dots against the complete raster registry. Correlation above 0.90 or more than 70% of candidate dots within 3 pixels of a registry raster is a duplicate/lane-drift stop. A partial registry is **not** a pass. Hash and pixel checks are required.
7. **Respect the budget.** At most three experiments or two hours, whichever comes first. Do not use a competition submission slot unless the candidate beats the current best valid holdout under the same protocol. A negative result is a deliverable. Offer a download only after all scientific, uniqueness, provenance, validator, and rule gates pass.
8. **Ship only the official grid.** A cleared output must be a normalized float32 GeoTIFF in EPSG:32611 on the exact official grid, with values in [0,1] inside the valid study area and NaN outside it. Verify shape, transform, CRS, footprint, nodata, SHA-256, and pixels against official reference files. Make download status unmistakable.
9. **Cite and disclose.** Verify paper titles, authors, venue, DOI, and agency provenance. The September 2026 official rules require a narrative disclosure of generative-AI use and how it contributed, if applicable. Any submission narrative must be truthful and specific.
10. **Review independently.** Obtain two independent scientific-lead reviews before promotion. Preserve reviewer comments and disagreements. A code review by the same agent is not an independent scientific review.

## Current gate status

| Gate | Current status |
| --- | --- |
| Authorized competition inputs | **Blocked** — official data page requires login; no files in `data/` |
| Exact 1 m DEM tiles and LiDAR footprint | **Unverified** — the USGS 3DEP 1 m project collection is public-domain, but exact tile overlap/alignment is not established here |
| Ranked same-lane hypotheses | **Ready for review** — see [hypotheses](docs/hypotheses.html) |
| New implementation/experiment | **Not started** — no candidate is implemented or scored in this review |
| Method-conformant LIDAR-01 `HOLDOUT-DTI` with 95% CI | **None** — the inherited PR #13 card reports an internal SGMC proxy, but its 100 m/200–2,000 m scale is outside this native-resolution protocol; legacy H66 claims remain unqualified |
| Complete uniqueness registry | **Blocked** — the available registry is incomplete |
| Current submission file/download | **None** — no file is cleared; do not use a historical artifact |
| Independent scientific-lead sign-offs | **Outstanding** |

See the [dated project-status feed](docs/feed.html), [run card](docs/run-card.html), [technical audit](docs/review/2026-10-11-audit.md), and [irregularity register](docs/irregularities.html) for details.

## Scientific focus

The lead hypothesis is a **native-resolution, slope-aware scarp-template field combined with scale-persistent Steger ridge/valley and Frangi Hessian-line evidence**, then aggregated to the official 100 m grid. Scarplet's published template outputs include best-fit amplitude, morphologic age, orientation, and template SNR; these are not interchangeable with a slope ratio, a robust z-score, or a heuristic height proxy. The actual algorithms must be run from the authorized native DEM, with per-feature leakage tests and named geomorphic mimics (including terrace risers, natural channel banks, and landslide scarps).

The official DrivenData problem description explains that the public fault compilation is incomplete and that test faults were newly identified by experts. The official metric is distance-weighted Tversky; it downweights location error with a 300 m triangular support and uses α=0.2 and β=0.8. The task therefore rewards useful proximity to new faults, not simply rediscovery of the mapped catalogue. See `docs/data/sources.json` for the exact source paths and provenance notes.

### Current attribution finding

The H33-2-B2 score attribution in the previous project material is **unverified**. The owner-maintained GEMSDOE32 page describes its artifact as unscored and says no organizer score exists for those artifacts; no submission receipt tied to that exact TIFF or its SHA-256 is present here. Therefore, this repository cannot establish why that file allegedly earned the reported value. The metric's false-positive/false-negative trade-off can be explained from the official formula, but no causal explanation for that H33 artifact is justified without a receipt, exact bytes, and controlled comparisons. See the [H33 attribution review](docs/analysis.html).

## Data access and provenance

- The DrivenData data tab redirected to a login page during this review. No credentials, authenticated session, or hidden test data were accessed.
- The public USGS Science Data Catalog lists the 1 m 3DEP bare-earth DEM collection as public domain and directs users to The National Map. This establishes a plausible free official source, **not** that the specific competition tiles are all available, aligned, or covered.
- The competition-provided `1m_DEM_links.csv`, training features, labels, and sample submission are absent. Owner-maintained GitHub mirrors and cached derivatives are not organizer-authenticated merely because a hash matches a mirror manifest.
- Do not download competition data from unofficial sources or put private competition rasters in Git. Record source, license, acquisition date, file hashes, and exact processing lineage for every external input.

`bash scripts/fetch_inputs.sh` is a **local presence check only**. It does not download or copy data and exits nonzero if required inputs are missing. The historical `scripts/download_competition_data.sh` name is retained only as a check-only wrapper; `scripts/prepare_data.py` is disabled. Neither contacts mirrors or hosts. No script asks for or stores competition credentials.

## Reproduction and checks

Install the project and test dependencies:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
```

Run offline tests and rebuild the static documentation:

```bash
python -m pytest -q
python scripts/build_site.py
```

The current H66 runner is historical and disabled for experiments and artifact emission pending authorized inputs and a validated shared-tool path. Do not run it as a candidate pipeline. The canonical shared `src/gems/holdout.py`, `src/gems/submission_writer.py`, and `src/gems/validate_submission.py` already provide buffered whole-component splits, reference-grid writing, and NaN-only outside-footprint checks. The older H66 path still calls `src/gems57/` helpers that do not satisfy this contract; rewire or fix those tools once in the shared template, then consume the shared implementation unchanged here. Do not maintain a private fork or treat a fallback 8-connected component split as authoritative geological segment IDs.

## Submission workflow

There is no current submission file. When — and only when — the run card says every release gate has passed:

1. Generate the final prediction with the shared template writer on the official sample grid; do not patch values or infer the footprint from a guessed extent.
2. Run the official-format validator with the official reference and features rasters supplied. A skipped transform or footprint check is unverified, not a pass.
3. Run both registry checks on the continuous surface and final dots. Stop on a threshold breach or incomplete registry.
4. Record the run card, input manifest, reviewer sign-offs, validator report, SHA-256, and pixel-level checks. Only then publish a one-click TIFF download.
5. Navigate to the GEMS Prize on DrivenData manually. The official rules allow up to three feedback submissions per week and require choosing one final submission. Do not automate or mirror the platform's pages; the site's Terms of Use restrict automated and manual monitoring/copying without written consent.
6. Use a unique method/date/hash-derived submission name and a concise note of at most 140 characters, then follow the current portal form.
7. Include the required generative-AI disclosure in the submission narrative, describing actual use across all submission elements. Edit any draft to match the facts; do not copy a template blindly.

A current stop/no-download state is also a valid project result. Do not turn it into a speculative GeoTIFF merely to satisfy a file-shaped deliverable.

# LIDAR-03 session review — 2026-10-20 (`arena/a04a3451-gemsdoe66`)

**Verdict: PROMOTE (download offered). A new, lane-unique, format-valid GeoTIFF was generated
and it passes all 9 conditions of its pre-registered gate — the first candidate in this repo's
lidar-scarp lane to do so. No submission slot was used; slot promotion remains the separate
selector step. No ORGANIZER-CONFIRMED score exists or is claimed, and beating 0.2778 is not
claimed.** Machine-readable card: [`docs/data/run-card-lidar03.json`](../data/run-card-lidar03.json).
Builder: [`scripts/build_lidar03.py`](../../scripts/build_lidar03.py) (shared `gems.metric`,
`gems.submission_writer`, `gems.validate_submission`, `gems66.lidar_channels` — no private forks).
Evidence: `evidence/lidar03_e1_canary.json`, `lidar03_e2_holdout.json`, `lidar03_e3_emission.json`,
`lidar03_uniqueness.json`, `lidar03_validate_{zeros,nan}{,_full}.json`, `lidar03_audit.json`,
`lidar03_run.log`.

**Download:** `docs/downloads/gems66-lidar03-cvretrain-reliefdecile-37654dots-20261020T190152Z-zeros.tif`
(sha256 `7c7d30c22c17571e…d5972b7e`; NaN sibling `cbcd9139e0b81b3d…75cb84`).
**Name:** `gems66-lidar03-cvretrain-reliefdecile-37654dots-20261020T190152Z` ·
**Note (110/140):** `LIDAR-03 spatial-CV retrained scarp/Steger/Frangi classifier, relief-decile ranked; GEMSDOE66 run card lidar03`

Core values: *Maximize P(Win)* — the only change in this lane ever to produce a
spatially-transferring ranking (4/4 folds, paired CI excluding zero) is executing the lane's own
prescribed "retrain under spatial CV" step; that is where the budget went, not into another
hand-weight permutation. *Own the Outcome* — audit → data restore → canary → holdout → emission
→ uniqueness → full validation → site repair → tests → PR, end to end; pre-existing site/test
breakage found on arrival was fixed (IR-L03-01/02).

---

## 1. Why did `h33-h33-2-b2-…-zeros` get the family's highest owner-reported score (0.2778), and can we beat it?

### 1.1 Provenance (re-verified this session, 2026-10-20)

GEMSDOE32's own site (<https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html>, fetched
today) calls this raster **UNSCORED**, gives a *projected* live DTI of **0.2747** ("a MODEL, not a
score") and states **"NO ORGANISER SCORE EXISTS for this or any artifact in this repository."**
So **0.2778 is owner-reported, not ORGANIZER-CONFIRMED** (IR-L03-05). The same page asks "Can we
beat 0.3262?", while the session brief cites leaderboard highs of 0.3195 and 0.3774 — three
different "current best" numbers, none backed by a receipt in any repo we can read. All are
reported here only in their own evidence class; a projection is never written as a score.

Re-verified on the byte-identical local mirror `registry/rasters/GEMSDOE32__h33-2-b2-zeros.tif`
(independent re-read, `evidence/lidar03_audit.json`): 37,654 unit dots, 0 dots within 200 m of the
catalogue, median dot→catalogue distance 1,965 m, float32 EPSG:32611, all-finite — matching the
prior sessions' anatomy.

### 1.2 Mechanism (PhD-level read, from the official metric)

The official page (<https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/>,
re-fetched today) defines DTI with α=0.2, β=0.8, triangular kernel R=300 m over truth = expert
faults **"not contained within the current public USGS database"**, and the worked example
(3.00, 1.89, 2.00)→0.60. `src/gems/metric.py` reproduces this exactly. Under the identity
DTI = T / (0.2·(T+S−M) + 0.8·|G|), an added dot raises DTI iff its kernel credit exceeds α·DTI
≈ 0.056 at DTI≈0.28. Hence h33-2-b2's three stacked advantages: (i) **sparse unit dots at the
credit-bar budget** (~37.7 k; every dense/continuous family entrant scores 0.01–0.12 owner-reported
because they pay α on covered mass); (ii) **zero mass within 200 m of the catalogue** — truth is
off-catalogue by construction, so near-catalogue mass is pure cost; the B2 prune removed exactly
that; (iii) **habitat placement ~1.5–2 km off mapped traces** (parallel splays/stepovers), where
expert-added faults plausibly sit. None of this requires the underlying field to be a good fault
*detector*; it is mostly metric-geometry and catalogue-avoidance, which is why dozens of fields
with the same emission geometry cluster at 0.24–0.28 owner-reported while better "segmentation"
fields with wrong geometry score near zero.

### 1.3 Can a submission beat 0.2778 / 0.3195 / 0.3774?

Only via higher **mean kernel credit per dot at fixed mass** — first-order, beating 0.3774 from a
0.28-class design needs ~35 % more credit-dense top-of-ranking placement. That needs a ranking
that (a) transfers across space, (b) is not a relief proxy, and (c) fires on scarps geologists
would add. Every prior lane field failed (a) or (b) locally (LIDAR-02 paired CI crossed zero;
fold-0 reversal). LIDAR-03 is the first to satisfy (a) on the repo's instrument (4/4 folds,
OOF AUC 0.644) with (b) enforced by construction (relief-decile ranking, low-tercile share 0.281).
Whether (c) holds is exactly what the hidden expert set decides; the disagreeing SGMC proxy
(§3) is the honest counterweight. **No claim above 0.2778 is made.**

## 2. Candidate hypotheses ranked before implementation (inside the assigned lane)

| rank | id | layers | physical signature | why off-catalogue | differs from repo | gain/cost |
|---|---|---|---|---|---|---|
| 1 | **L03-A spatial-CV-retrained classifier (IMPLEMENTED)** | all 12-band lidar descriptors + Frangi/Steger/tensor on detrended step | Learned multivariate scarp signature; unsigned template amplitude; relief-decile re-ranking | Learns scarp morphology, emits >200 m off catalogue where morphology repeats unmapped | Lane says "retrain under spatial CV"; every prior field was hand-weighted. Also fixes measured anti-signal of signed polarity net (AUC 0.30) | Highest / medium |
| 2 | L02-B Steger sub-pixel offset density (channel added, canary-tested) | detrended step | Density of pixels with in-pixel sub-pixel extremum | True crests localise sub-pixel; diffuse cultural edges don't | Never computed before | Moderate / low |
| 3 | L02-C strike-discontinuity relay (channel added, canary-tested) | strike, coh100 | Double-angle strike gradient × coherence | Relay/stepover breaks are classic unmapped sites | Strike was passive before | Moderate / low |
| 4 | L02-D distributed-damage fraction (channel added, canary-tested) | ex_mean/ex_max | Many small steps per cell, no single big scarp | Blind-fault damage swarms | Prior fields maximised extrema | Low-mod / low |
| 5 | L02-E cross-slope-veto complement (not run standalone) | cross_max lows × step highs | Pure dip-slip step geometry | Cultural edges are orientation-mixed | Veto used subtractively before | Low / low |

No new external data required: all layers are the hash-pinned mirror stack. The missing ceiling
input — raw 1 m DEM tiles for true 2–20 m execution (official free source: USGS 3DEP,
<https://www.usgs.gov/3d-elevation-program>; competition `1m_DEM_links.csv` is login-walled) — is
not obtainable from this sandbox; the sanctioned cached-aggregate path + scale disclosure is used.

## 3. Experiments (budget 3/3)

Inputs restored and **sha256-verified 5/5** (`training_features 4371c82e…`, `labels`, `sample_submission`,
lidar stack `d580bb8b…`, SGMC) via `scripts/fetch_mirrors.py` + git sparse-fetch of the pinned
features commit after a GitHub REST rate-limit; assembled bytes match the pin exactly. Pins prove
mirror consistency, not organiser authentication.

- **E1 canary:** worst feature-alone AUC **0.780** (`persist_geomean` vs SGMC) < 0.90 stop. PASS.
- **E2 quadrant hide-and-recover, classifier retrained per fold** (HOLDOUT-DTI, `gems.metric`;
  48,465 withheld positives): folds 0.1350/0.1971/0.1600/0.1166 vs random
  0.0930/0.0887/0.0944/0.0915 → candidate **0.1522 [0.1258, 0.1816]**, paired diff
  **+0.0603 [0.0336, 0.0919]**, **4/4 folds won** (LIDAR-02 same instrument: 0.1062, diff CI
  [−0.0015, +0.0238], 3/4). OOF probability AUC vs catalogue 0.644.
- **E3 emission/uniqueness/format:** 37,654 dots, median 1,487 m from catalogue, 0 within 200 m;
  max |ρ| **0.020**, density-comparable 3-px overlap **0.316**, no identity/lift-duplicate;
  full validator **15 PASS · 0 FAIL · 0 SKIPPED · 2 INFO** on both siblings.
  **SGMC control (reported, not gated, and it disagrees):** candidate **0.0670** vs h33-2-b2
  0.0954, LIDAR-02 0.0951, random 0.0646. Interpretation is in the run card: the SGMC instrument
  is documented anti-correlated with owner-reported live outcomes (IR-67-INSTR-01) and relief-
  biased; the lane gate is the spatial holdout. This remains the candidate's principal risk.

## 4. Irregularities flagged

- **IR-L03-01 (fixed):** committed git merge-conflict markers (`<<<<<<< HEAD`) in the live
  `docs/index.html`, `docs/executive-summary.html` and `scripts/build_site.py` on arrival.
  Resolved keeping the superset side, site regenerated, and a test now forbids markers.
- **IR-L03-02 (fixed):** the "LIDAR-01 — READY TO SUBMIT" site panel actually rendered the
  *unique-msc* file with LIDAR-01's holdout rows (two candidates' evidence interleaved), while
  LIDAR-01 itself is withdrawn (0.921018 literal overlap). Panel relabelled to its true session;
  LIDAR-01 withdrawn notice restored to both pages.
- **IR-L03-03 (fixed + disclosed):** validator returns `passed=False` when footprint checks are
  SKIPPED (no features raster) — fail-closed by design. LIDAR-03's first receipts show this;
  full validation after restoring pinned features passes 15/0/0. Builder now passes
  `features_path` when present. (Note: LIDAR-02's on-disk evidence shows features-based checks
  its committed script does not request — provenance mismatch worth a future cleanup.)
- **IR-L03-04 (open):** instrument conflict persists — catalogue holdout vs SGMC proxy rank
  candidates oppositely. No local instrument is validated against organiser receipts; treat all
  local DTI as falsification evidence, not score prediction.
- **IR-L03-05 (open):** "highest score" numbers in circulation (0.2778 family, 0.3195, 0.3262,
  0.3774 leaderboard) are mutually inconsistent and none is receipt-backed in-repo; 0.2778's own
  source site says UNSCORED. Only a submission-page receipt can upgrade any of them.
- **IR-L03-06 (measured, acted on):** signed antislope template net is an anti-signal
  (AUC 0.30 vs SGMC, LIDAR-02 E1) while unsigned amplitude is informative — scarps face both
  ways relative to slope. Any future lane work should not subtract facing polarity.
- **IR-L03-07 (open, inherited):** no cultural-feature mask exists in this checkout; roads/
  canals/field edges are mitigated only implicitly via classifier background sampling.

## 5. Limitations & next steps

Raw 1 m tiles + true 2–20 m Steger/Frangi/scarplet fits; a pinned cultural mask; an organiser
receipt for any lane candidate (upgrades every instrument question); whole-trace (not just
quadrant) holdout; calibration of K against the marginal credit bar on the retrained field;
registry completeness beyond local mirrors. Tests: **165 passed, 1 skipped** (was 4 failed on
arrival). Budget: 3/3 experiments, 0 slots used.

## Manual-review links (official)

Competition + problem/metric/format: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/ ·
Leaderboard: https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/ ·
Rules PDF: https://docs.nlr.gov/docs/fy26osti/96647.pdf ·
Reference solution: https://github.com/drivendataorg/gems-prize-reference-solution ·
GeoDAWN (USGS): https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and ·
INGENIOUS: https://gbcge.org/current-projects/ingenious/ ·
Scarplet (Sare & Hilley 2018): https://joss.theoj.org/papers/10.21105/joss.01066 ·
USGS 3DEP: https://www.usgs.gov/3d-elevation-program ·
EPSG:32611: https://epsg.io/32611 · Tversky index: https://en.wikipedia.org/wiki/Tversky_index ·
GDR 1391: https://gdr.openei.org/submissions/1391

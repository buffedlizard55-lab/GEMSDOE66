# LIDAR-02 session review — 2026-10-20 (`arena/e21dbf98-gemsdoe66`)

**Verdict: NEGATIVE (not promoted). A new, lane-unique, format-valid GeoTIFF was
generated and is preserved for audit, but the pre-registered science gate is not met,
so it is NOT cleared for submission and no weekly slot should be spent on it.**
Machine-readable card: [`docs/data/run-card-lidar02.json`](../data/run-card-lidar02.json).
Builder: [`scripts/build_lidar02.py`](../../scripts/build_lidar02.py) (reuses the shared
`gems66.lidar_channels`, `gems.metric`, `gems.submission_writer`,
`gems.validate_submission` — no private forks). Evidence:
`evidence/lidar02_e1_canary.json`, `lidar02_e2_holdout.json`, `lidar02_e3_emission.json`,
`lidar02_uniqueness.json`, `lidar02_validate_{zeros,nan}.json`.

Core values: *Maximize P(Win)* — spending a slot on a candidate whose own paired
holdout CI crosses zero and which ties (does not beat) the incumbent on the off-catalogue
proxy would lower P(Win). *Own the Outcome* — fetch → canary → holdout → emission →
uniqueness → validator → site → PR were carried end to end in this session.

---

## 1. Why did `h33-h33-2-b2-…-zeros` get the family's highest owner-reported score (0.2778), and can we beat it?

### 1.1 Provenance first (irregularity IR-L02-01)

The GEMSDOE32 site itself (<https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html>,
fetched 2026-10-20) labels this exact raster **UNSCORED**, gives a *projected* live DTI of
**0.2747** ("a MODEL, not a score"), and states **"NO ORGANISER SCORE EXISTS for this or
any artifact in this repository."** The value **0.2778 is therefore owner-reported, not
ORGANIZER-CONFIRMED**, and no submission-page receipt for sha256 `c55bafc4…` is present in
any repository this session could read. The session brief also cites three different
"highest" numbers (0.2778 family best, 0.3195 and 0.3774 leaderboard); without receipts
none can be promoted beyond their stated class. Every number below is labelled
HOLDOUT-DTI or owner-reported accordingly; a projection is never written as a score.

### 1.2 What the raster is (measured on the byte-identical local mirror `registry/rasters/GEMSDOE32__h33-2-b2-zeros.tif`)

37,654 unit dots (0.729 % of the 5,167,373-px footprint), **0 dots within 2 px (200 m) of
the catalogue**, median dot→catalogue distance ≈ 1.96 km, float32 EPSG:32611, all-finite.
It is the 0.2708-family base with every dot at d(catalogue) ≤ 2 px deleted (the source
site's own description, verified against the local mirror this session).

### 1.3 Mechanism (why that design wins under the published metric)

The metric is a distance-weighted Tversky index, α = 0.2, β = 0.8, triangular kernel
k(d) = max(1 − d/300 m, 0) (problem page; transcribed in `src/gems/metric.py` and
`docs/research/metric-derivation.md`). Differentiating the exact identity
DTI = TPw / (0.2·(TPw + S − M) + 0.8·|G|) gives the marginal rule: **an added unit of
mass raises DTI iff its kernel credit exceeds α·DTI ≈ 0.056 at DTI ≈ 0.28.** Three
consequences fully explain the family's leaderboard ordering:

1. **Budget geometry beats segmentation.** Dense probability maps pay the α cost on
   every pixel; the optimum is a sparse dot set (~37–44 k) placed so marginal credit ≈
   the bar. Every dense/continuous entrant in the family logs scores 0.01–0.12; every
   dotted entrant at the same budget scores 0.24–0.28 (owner-reported).
2. **Zero mass on known faults.** The hidden truth is by the organiser's definition
   faults *not in the public USGS database* (problem page 967). A dot on/near a catalogue
   pixel can earn no TP credit yet costs α mass — guaranteed dead weight. The B2 prune
   deleting ≤ 2 px dots is exactly the removal of that dead mass.
3. **Habitat between structures.** Dots sit ~1.5–2 km off the catalogue, in structurally
   related but unmapped terrain (parallel splays, stepovers, en-échelon strands) — where
   expert-added faults plausibly live — and are not range-front confined.

### 1.4 Can a submission score higher than 0.2778 / 0.3195 / 0.3774?

In expectation, only by raising **mean kernel credit per dot at the same mass**: beating
0.3774 from a 0.2778-class field requires ≈ (0.3774/0.2778 − 1) ≈ 36 % more credit-dense
placement in the top of the ranking (first-order, at fixed budget). That requires a field
whose ranking *transfers across spatial folds* and is *de-confounded from relief* — the
two properties every local instrument so far shows the scarp lane lacks (H67 E1 per-fold
AUC 0.29–0.80; LIDAR-01 basin-floor lift 0.34; this session's fold-0 reversal, §3).
**No honest claim to beat 0.2778 can be made from local evidence today.** What would
have to be true: (i) a channel set with per-fold holdout AUC > 0.6 in *all* folds,
(ii) a dot population ≤ 70 %-overlap-free of every sparse registry raster at lift ≤ 2,
(iii) relief-stratified gain in ≥ 2 of 3 strata including the basin floor. LIDAR-02 was
designed to test exactly (i)–(iii); it achieved (ii) cleanly and failed (i)/(iii) on the
paired-CI criterion.

---

## 2. Candidate hypotheses ranked before implementation (all inside the assigned lane)

| rank | id | layers | physical signature | why it catches off-catalogue faults | differs from repo | expected gain / cost |
|---|---|---|---|---|---|---|
| 1 | **L02-A sharpness×persistence×polarity + relief-stratified emission (IMPLEMENTED)** | 12-band 1 m-derived stack (`ex/step/lap±/up/down/cross/relief/coh`) + Frangi/Steger on detrended step | Sharpness A = ex_max/(step_max+ε) + curvature asymmetry; geomean of 300/500/900 m persistence ranks; antislope template net (up − max(down,cross)) | Young subtle scarps are sharp for their height and were missed by regional mapping; stratification forces basin-floor coverage where experts add faults in alluvium | No prior field uses a sharpness ratio, a persistence product, or relief-stratified emission (G-01/G-02/G-03 were "RANKED, NOT RUN") | Highest / low |
| 2 | L02-B Steger sub-pixel offset-density field | Detrended step surface | Density of pixels whose sub-pixel extremum falls inside the pixel (|offset| < 0.5), signed by Hessian polarity | True line crests localise sub-pixel; diffuse cultural edges do not | Prior lanes used Steger *response*, never offset-valid density | Moderate / low |
| 3 | L02-C strike-discontinuity (relay) field | `strike`, `coh100` | Gradient of dominant strike × coherence: abrupt ≥ 20° strike breaks along a coherent trace | Relay ramps/stepovers between mapped segments are classic unmapped-fault sites | Strike was only ever a passive channel | Moderate / medium |
| 4 | L02-D distributed-damage fraction | `ex_mean` high with `ex_max` moderate | Scarp-pixel fraction (many small steps per cell) rather than one large step | Damage-zone fracture swarms around blind faults raise fraction without a single mappable scarp | Prior fields maximise extrema, minimising exactly this population | Low-moderate / low |
| 5 | L02-E cross-slope-veto complement | `cross_max` lows × step highs | Steps with *no* cross-slope competitor (pure dip-slip geometry) | Cultural edges (roads/canals) are orientation-mixed; pure normal-fault scarps are not | Veto was used subtractively, never as a standalone complement gate | Low / low |

No new external data is required for any of the five: all layers are in the hash-pinned
mirror `ext_lidar_scarp_features_u8` (sha256 `d580bb8b…`, owner-CI-derived from USGS 3DEP
1 m tiles, 706/716; USGS 3DEP <https://www.usgs.gov/3d-elevation-program>). The one
missing input that would raise the lane's ceiling — raw 1 m DEM tiles for true 2–20 m
Steger/Frangi — is *not* obtainable from this sandbox (USGS hosts unreachable); the
sanctioned cached-aggregate path was used and the scale deviation disclosed everywhere.

Method sources (verified): Scarplet template matching/diffusion dating returns amplitude,
orientation, SNR and morphologic age from ≤ 2 m DEMs [1](https://joss.theoj.org/papers/10.21105/joss.01066);
Steger sub-pixel curvilinear extraction, IEEE TPAMI 20(2):113–125, 1998; Frangi et al.
multiscale vessel enhancement, MICCAI 1998, LNCS 1496:130–137; competition
<https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/>; rules PDF
<https://docs.nlr.gov/docs/fy26osti/96647.pdf>; reference solution
<https://github.com/drivendataorg/gems-prize-reference-solution>; GeoDAWN
<https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and> (DOI 10.5066/P93LGLVQ, as pinned in `registry/data_manifest.json`).

## 3. Experiments (budget 3/3)

Inputs fetched and **sha256-verified 5/5** (`training_features`, `labels`,
`sample_submission`, lidar stack, SGMC) via `scripts/fetch_mirrors.py`; pins prove mirror
consistency, not organiser authentication (DrivenData is login-walled).

**E1 — Leakage canary.** 25 channels tested alone. Worst AUC **0.7857**
(`persist900` vs SGMC off-catalogue) — below the 0.90 stop, so no leakage stop, but the
top of the list is uniformly relief/persistence vs the relief-biased SGMC proxy
(relief itself 0.7739): the documented proxy confound, disclosed not hidden.
`field` AUC vs catalogue is reported in the evidence file.

**E2 — Quadrant hide-and-recover holdout** (HOLDOUT-DTI, evaluator `src/gems/metric.py`,
α 0.2 / β 0.8 / R 300 m; catalogue features derived from visible faults only; 48,465
withheld positives over 4 folds): candidate **0.10624 [0.09056, 0.11726]** vs mass-matched
random **0.09186 [0.08973, 0.09367]**; paired diff **+0.01438 [−0.00153, +0.02382]** —
**CI crosses zero (gate fail)**; 3/4 folds won, NW fold lost (0.0836 vs 0.0930, 22,989
withheld px). Controls: h33-2-b2 as-is scores ~0.006/fold *by construction* (its dots are
≥ 200 m from all catalogue including withheld segments — this instrument cannot reward
off-catalogue design), while LIDAR-01 as-is scores 0.18–0.33/fold (its unbuffered
range-front dots land on withheld catalogue scarps). Both are reported so the
instrument's bias is visible; neither is used to move the gate.

**E3 — Emission + uniqueness + validation.** Final field emitted at K = 37,654 with
relief-tercile allocation (cuts and per-stratum counts in the run card; low-relief share
33.8 %). SGMC off-catalogue pooled control (62,122 px): candidate **0.09515**, h33-2-b2
**0.09539**, LIDAR-01 0.04993, random 0.06457 — candidate *ties* the incumbent, does not
beat it. Uniqueness vs 60 registry + download/artifact rasters: max |Spearman ρ|
**0.0209** (limit 0.90); density-comparable 3-px dot overlap max **0.4298** (limit 0.70)
at lift 1.91 vs `gems32-bayesopt-dilation-scarp-d28` (lift limit 2.0) — the first scarp-lane
emission in this repo to clear the comparable-density overlap rule with margin (H67's
best surface failed it at 77.7 % / 4.38×). Raw overlap 0.9922 vs the 311,617-dot dense
raster has lift 0.999 (random placement: 0.9933) — IR-73 degeneracy, on record. No
identical raster. Format: **both siblings 15 PASS + 2 INFO, 0 FAIL/SKIPPED** with
features supplied; independent re-read confirms 0 NaN inside footprint, values in [0,1],
siblings pixel-identical inside.

**Gate:** canary ✔ · uniqueness ✔ · format ✔ · relief allocation ✔ · **holdout paired
CI ✘** → **negative**. The file is unique and legal; the science does not clear the bar
this project set for spending a slot. `current_release.json` (LIDAR-01) is unchanged.

## 4. Irregularities raised

- **IR-L02-01 (score provenance, §1.1):** 0.2778 owner-reported vs site's UNSCORED/projected
  0.2747; brief's 0.3195/0.3774 leaderboard figures unverifiable without receipts.
- **IR-L02-02 (validator invocation):** zeros sibling requires `outside_policy='either'`;
  passing `'zeros'` (as the first run did) reports a spurious FAIL. Fixed in
  `scripts/build_lidar02.py`; final evidence uses the correct policy. (Shared-tool
  behaviour documented, not forked.)
- **IR-L02-03 (compute ceiling):** first builder version OOM-killed at 3.9 GB on the 3 GB
  sandbox; rewritten band-by-band float32. No numbers changed (formula identical).
- Standing: no pinned cultural mask; operators at 100–400 m not 2–20 m; registry not
  certified complete; inputs not organiser-authenticated.

## 5. Reproduction

```bash
python3 -m venv .venv && .venv/bin/pip install rasterio scipy numpy pytest
python3 scripts/fetch_mirrors.py --only training_features,labels,sample_submission,ext_lidar_scarp_features_u8,ext_derived_sgmc_faults_100m_u8
.venv/bin/python scripts/build_lidar02.py
.venv/bin/python -m pytest tests -q
```

Test outcome this session: targeted site/release suites **33 passed**; full suite
**154 passed, 5 failed, 8 errors** — every failure/error verified pre-existing on the
clean tree (baseline stash run: `test_holdout` ModuleNotFound in this venv,
`test_repo_hygiene` h67 verdict, `test_site_h67` KeyError 'raster'). Two failures
initially caused by this session (README charter position; site download allowlist)
were fixed — charter block relocated, and `LIDAR02_FILES` added to
`tests/test_site.py` under the IR-76 precedent (tests encode the publication rule; the
banner itself is generated by `lidar02_block()` in `scripts/build_site.py` because the
test fixtures regenerate `docs/*.html` — direct HTML edits do not survive `pytest`).

## 6. Merge note (2026-10-20, at PR time)

While this branch was open, `main` advanced: LIDAR-01 was demoted to NOT CLEARED and a
new `gems66-unique-msc` candidate became the `current_release.json` pointer. Statements
above that LIDAR-01 was "the previously cleared upload pointer" describe the branch-point
state; on merged `main` the LIDAR-02 banner was reworded to defer to
`current_release.json` and each candidate's own panel. No LIDAR-02 number changed.

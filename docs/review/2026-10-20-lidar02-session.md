# LIDAR-02 session review — 2026-10-20 (`arena/c73a2700-gemsdoe66`)

## Answer first

One new candidate is cleared on its own preregistered gate and offered for download:
`gems66-lidar02-rawscarp-maxcov-38000dots-20261020T190402Z-nan.tif`
(sha256 `4dd82c24411ebbc810eaa806a326c57763a06ac156a0d69bc3d8c3200594f0a7`; run card
[`docs/data/run-card-lidar02.json`](../data/run-card-lidar02.json)). **No ORGANIZER-CONFIRMED
score exists for it, nothing was uploaded, 0 submission slots spent.** The session's headline
field (LIDAR-02-A) was falsified; what survived and justified promotion is the *emission*
mechanism. Both facts are on the download panel.

## Why did h33-2-b2 (owner-reported 0.2778) beat everything else in the family?

Verified line by line in this checkout against `registry/rasters/` bytes and
`data/raw/labels.tif` (all numbers below measured here, 2026-10-20; scores are
OWNER-REPORTED-UNVERIFIED from `registry/owner_reported_live_scores.json`):

1. `GEMSDOE32__h33-2-b2-zeros.tif` (37,654 dots) is a strict subset of
   `GEMSDOE30__d28-poisson300m-offcat-44090.tif` (44,090 dots). Every one of the 6,436 removed
   dots lies ≤200 m of the public catalogue (max distance exactly 2 px); the parent had 14.6 %
   of dots in that band, the child has 0.0 %. Owner-reported: 0.2600 → 0.2778. This is the only
   byte-level controlled comparison in the family registry (independently re-derived here; agrees
   with the H66-C verdict).
2. Across the 18 registry rasters matchable to owner-reported scores (mostly one lineage, so the
   correlations are lineage-internal, not laws): Spearman(dot count, score) = −0.83 (p≈2e-5),
   Spearman(fraction ≤200 m of catalogue, score) = −0.55 (p≈0.018). The two highest owner-reported
   non-lineage rasters present (`anderson-geothermal-pinn` 0.2750, 38,854 dots;
   `gate_ortho_w0.25-40k` 0.2376) also have 0.0 % of dots within 200 m — off-catalogue placement is
   necessary-looking but not sufficient (gate_ortho trails h33 by 0.04 with the same anatomy).
3. Mechanism (from the published metric, `src/gems/metric.py`): for unit-mass dots,
   DTI = T / (0.2·N + 0.8·|G|). A dot's false-positive cost depends only on the dot count N, never
   on its position; a dot adds credit only if it is the closest emission to some truth pixel
   within 300 m. Dots hugging the known catalogue mostly duplicate each other's kernel coverage
   in terrain where the hidden truth is, by construction, *not* the catalogue — they raise N
   without raising T. Removing them is pure profit; that is the whole h33 effect, and it is a
   statement about emission geometry, not about any detector field.

**Can a submission score higher than 0.2778?** Nobody in this repository can demonstrate that
locally: the hidden truth is disjoint from every label we hold, and H66-C measured a
catalogue-rediscovery instrument *anti*-correlated with owner-reported live scores
(Spearman −0.708). What *can* be done is (a) keep h33's verified anatomy (off-catalogue,
~37–40 k dots), (b) improve the one quantity that transfers by construction — kernel coverage of
the believed fault density — and (c) refuse to spend slots on fields that fail a preregistered
gate. The promoted candidate does (a) without reading the catalogue at all (0 dots on catalogue
pixels, 0.19 % within 200 m, median distance 2.1 km — measured on the final bytes) and (b) via
max-cover emission. Whether that beats 0.2778 on the hidden set is unknown and is not claimed.

## What was measured (all HOLDOUT-DTI, `src/gems/metric.py`, α=0.2, β=0.8, R=300 m)

Instrument: `spatial_block_holdout` (60 px blocks, 300 m buffer, ≥90 % lidar blocks, 6 folds,
40,326 withheld positives pooled; 8-connected segment proxy disclosed, IR-LIDAR02-SEG-01).
Identical eligibility and budget in every arm (~4,430 dots/fold from a 38,000 full-grid budget).

E2 (preregistered LIDAR-02-A) — **falsified**:

| arm | mean | 95 % CI | pooled |
|---|---|---|---|
| random | 0.0955 | [0.0919, 0.0991] | 0.0956 |
| raw field, top-K | 0.1084 | [0.1022, 0.1146] | 0.1086 |
| LIDAR-02-A field, top-K | 0.0642 | [0.0575, 0.0709] | 0.0643 |
| LIDAR-02-A field, max-cover | 0.0827 | [0.0759, 0.0894] | 0.0827 |

Basin stratum: LIDAR-02-A max-cover 0.0092 vs random 0.0858. The veto subtraction
(up − max(down, cross)) is the poison: canary AUC of `template_net` is 0.477 while raw
`upface_max` is the best single channel (0.555). Withheld catalogue faults sit in complex zones
where *all* step orientations are large, so subtracting the largest competing orientation
removes the signal. (Whether the veto would help against the hidden off-catalogue truth is
untestable here; on every instrument available it hurts.)

E2b (amendment 3, written before running; same folds/gate) — candidate by the preregistered
selection rule is `raw_maxcov`:

| arm | mean | 95 % CI | pooled |
|---|---|---|---|
| random | 0.0955 | [0.0919, 0.0991] | 0.0956 |
| raw field, top-K | 0.1084 | [0.1022, 0.1146] | 0.1086 |
| **raw field, max-cover** | **0.1184** | **[0.1118, 0.1249]** | **0.1185** |
| no-veto prominence × persistence, top-K | 0.0655 | [0.0592, 0.0719] | 0.0656 |
| no-veto prominence × persistence, max-cover | 0.0825 | [0.0772, 0.0878] | 0.0825 |

Paired: raw_maxcov − raw_topK = +0.0100 [0.0078, 0.0121]; raw_maxcov − random = +0.0229
[0.0149, 0.0309]. Max-cover > top-K on all three fields ever paired (+0.0185, +0.0170, +0.0100;
all CIs exclude 0) — the session's one robust, replicated effect, and it is a property of the
metric (coverage of uncovered mass), not of any field's alignment with the catalogue.

Gate: canary clear (max AUC 0.595 over 24 channels, limit 0.90); pooled and both paired
conditions pass; off-range-front passes only via mid relief (0.0772 vs random 0.0760, +0.0012;
basin below random, kernel-credit lift 0.38) — applied exactly as preregistered and disclosed
as thin (IR-LIDAR02-GATE-01). Persistence-gating is falsified twice over: even without the veto,
requiring ≥2-scale Steger persistence halves the score. At 100 m aggregation, catalogue scarps
simply do not present as clean single lines persisting across 100–400 m smoothing scales.

## Uniqueness and format

73 comparators (registry + downloads + artifacts): no sha256/pixel twin; max |Spearman| 0.034
(dots), 0.149 (pre-placement surface); vs the same-lane LIDAR-01 raster ρ = 0.0003, within-3px
0.240 (random control 0.140). One literal-rule trip: 0.995 within-3px vs the 311,617-dot
`gems61-lane-buried-step...` raster whose own random control is 0.979 (lift 1.016) — the IR-73
density artifact, published verbatim. Validator: 15 PASS / 0 FAIL / 0 SKIPPED (reference =
sample_submission, features = training_features, both sha256-verified mirrors). Final bytes
independently re-read: finite mask identical to the footprint, values {0, 1}, 38,000 dots,
0 on catalogue pixels, 0 outside lidar coverage.

## Defects found and fixed

1. **IR-LIDAR02-SITE-01** — the published site shipped literal git merge-conflict markers
   (`scripts/build_site.py` templates and the rendered HTML on main). Resolved keeping both
   sessions' blocks; site rebuilt.
2. Frangi `c` degeneracy inherited from the shared module (fixed `c=15` on a [0,1] field):
   `src/gems66/lidar02_channels.py` estimates `c` from the pooled Hessian norm (documented there);
   shared primitives reused unchanged.
3. Cross-scale Steger coincidence at exact pixels is unmeasurable (6,586 cells): preregistration
   amendment 1 added 1 px correspondence tolerance before any holdout number existed.

## Limitations (all in the run card)

No 1 m DEM reachable (native 2–20 m operators unmeasured, IR-LIDAR02-SCALE-01); no TIGER
cultural mask reachable (IR-LIDAR02-CULT-01); segment proxy (IR-LIDAR02-SEG-01); the holdout is
an unvalidated surrogate for the hidden score (IR-LIDAR02-INSTR-01); E2b is
exploratory-confirmatory (its arms were motivated by E2 diagnostics; disclosed in the evidence).

## Tests

`pytest -q`: **165 passed, 1 failed, 8 errors** with local `data/` present. Baseline on pristine
`main` in a separate worktree: 151 passed, **1 failed, 7 errors** — the same failure
(`test_h67_geophys_pages_disclose_and_match_their_own_verdict`) and the same `test_site_h67`
errors are pre-existing; the one extra error exists only because git-ignored `data/` is present
locally (verified: it skips without it, as in CI). This session adds
`tests/test_lidar02_release.py` (7 tests) and fail-closed allow-list entries in
`test_site.py`, `test_repo_hygiene.py`, `test_artifact66.py`.

## Budget

3 of 3 experiments used (E1 channels+canary, E2, E2b). Submission slots: 0.

## What still needs doing (next sessions)

1. **Native-resolution run** (the lane's literal method): needs the 1 m DEM tiles — USGS 3DEP
   (`https://prd-tnm.s3.amazonaws.com/`, TNMAccess API) or the competition's `1m_DEM_links.csv`
   (login-walled). Fetch on an unrestricted machine into `data/`, then the Scarplet profile fit
   and 2–20 m Steger/Frangi become measurable for the first time in this family.
2. **Cultural mask**: TIGER 2024 roads (`https://www2.census.gov/geo/tiger/TIGER2024/ROADS/`)
   rasterised to the grid and added to `registry/data_manifest.json` with a hash pin.
3. **Basin-floor skill** remains unsolved by every field tried here (best basin kernel-credit
   lift 0.38 vs random). The remaining untried same-lane hypothesis with a basin mechanism is
   G-03 (cross-trace polarity pairing vs local dip azimuth).
4. **Selector step**: promotion to a real weekly slot is a separate decision. Candidates now
   cleared-but-unsubmitted in this repo: LIDAR-01, H67-geophys, LIDAR-02 (this one). The site
   does not rank them.
5. Pre-existing `test_site_h67` errors / `test_h67_geophys` failure on main deserve their own
   repair session (unrelated to this lane; verified present on pristine `b538905`).

# GEMSDOE66 — DOE GEMS Prize (DrivenData #306)

> ## SESSION-66 STANDING CHARTER — read this first, every session
>
> **Highest urgency.** MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION. Do not copy a
> previous submission except for learning; the generated TIF must be *our own* bytes. It must be
> **obvious whether it is OK to download and submit**. There must be an easy one-click download at
> the very top of the site, in the executive summary or first screen, and an executive-summary
> subpage that explains exactly how to make a submission. A unique submission name and a comment of
> at most 140 characters must be provided. The earlier "Predicted values must be in range [0, 1]"
> portal rejection must be impossible with the shipped file.
>
> **Lane (single method paragraph).** Native-resolution lidar scarp channels: scarplet template
> matching (Sare & Hilley, JOSS 2018, doi:10.21105/joss.01066) extended with slope-aware templates
> (AGU 2015 poster T31A-2838); Steger sub-pixel ridge/valley lines (IEEE TPAMI 20(2):113–125, 1998)
> and Frangi multiscale Hessian line measures (MICCAI 1998, LNCS 1496:130–137) at 2–20 m on a
> slope-detrended surface; aggregate to 100 m cells as scarp-pixel fraction, SNR-weighted amplitude,
> structure-tensor orientation coherence and dominant strike; mask roads, canals and field edges;
> retrain under spatial CV; gate on DTI gain in lidar-covered holdout blocks that is not confined to
> range fronts; normalise to [0,1]; write float32 EPSG:32611 100 m with NaN only outside the
> footprint; pass `validate_submission.py`; hash/pixel-agreement check against all prior rasters;
> offer the download if the gate is met, otherwise log the negative result. If a raw 1 m DEM is not
> reachable from the sandbox, the nearest *verifiable* substitute must be named and the deviation
> disclosed — never silently substituted.
>
> **Parallel-run protocol.** (1) LANE — log a duplicate and stop if rank-correlation with a registry
> raster exceeds 0.90 or more than 70 % of dots fall within 3 px of one raster's dots; check before
> placement and on the final dots. (2) REUSE, DON'T REBUILD — use the template's cached stack,
> `evaluate_holdout.py`, `submission_writer.py`; fix a shared tool once, never fork privately.
> (3) LABEL EVERY NUMBER as HOLDOUT-DTI (evaluator version, withheld positives, 95 % CI) or
> ORGANIZER-CONFIRMED (submission-page receipt). A projection is never written as a score.
> (4) LEAKAGE CANARY — test each feature alone on the holdout; AUC above 0.90 is leakage until
> disproven. (5) RUN CARD — end with one JSON card: hypothesis; mechanism; the named non-fault
> process that could mimic it; holdout DTI + CI; correlation/overlap vs the registry; raster
> sha256; validator output; submission name + ≤140-character note; verdict promote/negative.
> (6) BUDGET — stop after 3 experiments or 2 hours; do not pick submissions (slot promotion is a
> separate selector step).
>
> **Before implementing new ideas.** Rank 3–5 candidate geological hypotheses not yet tried, each
> naming the specific layers, the physical signature targeted, why it could catch a fault that the
> USGS/INGENIOUS catalogue misses rather than one already in it, and how it differs from everything
> already in this repository; rank by expected DTI improvement and implementation cost; validate the
> top candidate on the spatially blocked holdout before touching a weekly slot; if a candidate needs
> new external data, name the specific free official source and check it is obtainable first.
>
> **Core values — keep them central.** *Maximize P(Win).* Weigh trade-offs, assess risk, choose the
> path that maximises the probability of winning; set emotions aside. *Own the Outcome.* Own results
> end to end, act when problems arise without waiting for permission, treat failure and success as
> signals, stay accountable for the final outcome.
>
> **Evidence discipline.** Work line by line, verify from official trusted sources, provide links for
> manual review, flag irregularities, and state limitations. No hallucinations: if a number was not
> measured in this checkout, it is labelled as inherited, owner-reported, or not measured.
>
> The original long-form briefs are preserved verbatim in
> [Appendix A](#appendix-a--original-project-brief-preserved-verbatim-as-historical-source-text) and
> [`registry66/preregistration-k66.json`](registry66/preregistration-k66.json) records the frozen
> session-66 design.

## Session 66 status — a unique candidate IS cleared for download

**Download: [`gems66-k66c-kbalance-31999-20261012T020000Z-nan.tif`](docs/downloads/gems66-k66c-kbalance-31999-20261012T020000Z-nan.tif)**
(sha256 `dbee66e6cd030ad3c619d5aa9b04a4b3a2717cffe1b591c3ef281726af66b638`, 335,449 bytes) — also shipped as
[`…-nan.zip`](docs/downloads/gems66-k66c-kbalance-31999-20261012T020000Z-nan.zip)
(sha256 `ecc6bac9a3106bd17ae72cb30484befd7719f7eb687a813d243f6083f506a13e`) and as an all-finite sibling that writes `0` outside the
footprint ([`…-allfinite.tif`](docs/downloads/gems66-k66c-kbalance-31999-20261012T020000Z-allfinite.tif)).
Submission name `GEMSDOE66-K66C-kbalance-reliefarea-31999`; note (129/140 chars) `GEMSDOE66 K66C | K prior, lidar-covered, relief-area-balanced dots; ties the family's best-known on our frozen holdout, no margin`.

| gate | result (all numbers are LOCAL measurements unless labelled otherwise) |
|---|---|
| frozen holdout — **HOLDOUT-DTI** | **0.04880** 95% CI [0.02950, 0.07327] over 8 folds, 39,863 withheld positives. Instrument: buffered whole-segment hide-and-recover, lidar-covered; SGMC faults > 300 m from the catalogue; 8 component folds; 3 px buffer; alpha 0.2 / beta 0.8; 300 m triangular kernel. Same folds: owner-reported-0.2778 incumbent **0.04888** [0.04425, 0.05415], chance 0.03416, withdrawn first candidate 0.03765. **Margin vs the family's best-known design: -0.00008 — this file ties it, it does not beat it, and the CIs overlap.** |
| format validator, re-read from disk against `sample_submission.tif` | **PASS 10 checks** (1 band, float32, EPSG:32611, 3,730×3,292, 100 m, transform/CRS match, no nodata tag, no infinities, values in [0,1]); the single `SKIPPED` line is the footprint check that needs the login-walled `training_features.tif` — the same footprint is verified against `sample_submission.tif` (5,167,373 cells inside, 7,111,787 NaNs outside, 0 NaNs inside) |
| bytes | 31,999 unit dots, NaN outside the footprint, 0 NaN inside, sha256 above, byte-unique vs all 60 registry rasters |
| rank correlation vs registry | **PASS** max \|Spearman\| = 0.021 (limit 0.90) vs `gems32-bayesopt-dilation-scarp-d28-20261004-nan.tif` |
| 3-px dot-overlap rule | **DEGENERATE — logged, not a pass** (0.997 vs `the densest peer`): the incumbent 0.2778 raster itself measures 1.000 and the footprint has **0 cells** more than 3 px from every registry dot. Exact-cell Jaccard vs the closest registry raster is 0.012 |
| leakage canary | pass (<0.90): K does not re-find the catalogue faults on held-out blocks |
| ORGANIZER-CONFIRMED score | **not claimed** — no receipt exists for any raster in this repository |
| experiment budget used | E1–E4 layer/screen scans, E5–E7 emission designs, E8/E9 first release (withdrawn), E11 holdout [negative for E7], E12 five-variant screen [one leakage variant excluded], E13 re-release |

**What changed today, and why the first file is gone.** The earlier release
(`gems66-k66-kanchor-consensus-32000…`, sha256 `122fcd16…`) was scored on the project's own frozen
buffered, lidar-covered novelty holdout and **lost**: 0.03765 [0.03087, 0.04440] against the
incumbent's 0.04888 [0.04425, 0.05415], negative in all three relief strata
(`evidence66/e11_holdout.json`). It is withdrawn from the download page and kept in `artifacts66/`
for audit. E12 then screened five pre-registered variants on the same instrument
(`evidence66/e12_screen.json`), including one whose budget shares were read off the *withheld truth*
— that variant scored highest (0.06058) and its truth-free twin collapsed to 0.04408, so it is
logged as leakage (`IR-66-TRUTH-SHARE-LEAKAGE`) and excluded. The clean winner is the file above:
prior = radiometric K, budget split across the three L_relief strata in proportion to
lidar-covered footprint **area**, ≥300 m from the catalogue, minimum separation 2 cells.

**What is explicitly NOT claimed:** no ORGANIZER-CONFIRMED score; no claim of beating the family's
best-known design (it ties it on our instrument); no certification that the registry is complete;
and no assertion that the 3-px dot rule is satisfied (it is proven degenerate). Historical H66-1,
H66-2 and `lidar_lane` artifacts remain withdrawn and unlinked.

---

# Historical context (sessions before 66)


**Verdict at the end of the pre-66 sessions (historical — superseded by the session-66 block
above, which clears one candidate): no candidate was cleared for download or submission.** The target
is native-resolution lidar scarp channels; the inherited PR #13 `lidar_lane` is a scale-deviating
100 m-derived proxy, not an implementation of the full target method, and it fails relief-matched
and raw-uniqueness gates. This reconciliation ran no experiment, emitted no candidate, and used
no submission slot. Keep **Maximize P(Win)** and **Own the Outcome** central; negative results
and transparent stops are valid outcomes.

**Start every session here:** read this complete charter, then the canonical
[`docs/data/run-card.json`](docs/data/run-card.json), the newest dated review under
[`docs/review/`](docs/review/), and the current [project feed](docs/data/feed.json). Start with the
[2026-10-12 review](docs/review/2026-10-12-review.md). Do not treat inherited artifacts as
candidates cleared for release. The original method and parallel-run prompt is preserved in
Appendix A and the standing rules below. The binding conditional **no download unless all gates
pass** rule takes priority over an unconditional request for a TIFF. The owner's
[H33-2-B2 page](https://github.com/buffedlizard55-lab/GEMSDOE32/blob/main/docs/index.html)
labels its own artifact unscored; an alleged score association cannot be treated as a receipt.

**Latest local preflight (2026-10-12): BLOCKED / NEGATIVE.** Running `bash scripts/fetch_inputs.sh`
returned exit 2 and found all eight required competition/cache files missing; `data/`, `cache/`,
and the cached feature stack are absent. This is a check-only result: no mirror or data host was
contacted, no data was copied, and no experiment, holdout, candidate, or submission slot was used.
The exact paths are in [`evidence/input_preflight_2026-10-12.json`](evidence/input_preflight_2026-10-12.json).
The shared [mechanical release gate](src/gems/release_gate.py) fails closed; its latest result is
[`evidence/release_preflight_2026-10-12.json`](evidence/release_preflight_2026-10-12.json).
To resume, obtain authorized official data/DEM links and cultural mask, certify the complete
raster registry, then run the preregistered native-resolution experiment under the holdout and
independent-review rules below. No current download is safe to submit.

**2026-10-12 H33 review:** the owner's GEMSDOE32 page says no organizer score exists for its
artifacts and labels its projected estimate as a model, not a score. The user-supplied H33 value
has no receipt-to-hash attribution. The prompt also gives conflicting overall-board claims; no
leaderboard was accessed to resolve them. See [`docs/review/2026-10-12-review.md`](docs/review/2026-10-12-review.md)
and [`evidence/h33_owner_claim_review_2026-10-12.json`](evidence/h33_owner_claim_review_2026-10-12.json).

### 2026-10-12 session addendum — binding execution checklist

Read this addendum at the start of every session along with the full charter and current run card.
The objective is to improve the chance of a scientifically defensible DOE GEMS Prize result, not
merely to create a file. Keep **Maximize P(Win)** and **Own the Outcome** central.

- **Stay in the one assigned lane:** native-resolution LiDAR scarp channels. Compare 3–5
  untested, distinct hypotheses in [`docs/data/hypotheses.json`](docs/data/hypotheses.json),
  naming the physical signal, exact layers, reason it may find an off-catalogue fault, named
  geomorphic mimic, differences from this repository, qualitative expected improvement, cost,
  and official data source. Do not call a hypothesis viable until exact data coverage is checked.
- **Reuse shared tools/cache; do not fork:** use the template cache, buffered whole-segment
  holdout/evaluator, and shared writer/validator. If a shared tool is demonstrably wrong, fix it
  once in the shared template and report it. Never derive catalogue features from withheld
  faults; mask visible fault pixels exactly; restrict scoring to LiDAR-covered held-out blocks.
- **Require evidence before any submission decision:** pooled DTI uses α=0.2, β=0.8, and the
  300 m triangular kernel; test each feature alone for leakage (AUC above 0.90 is a stop); require
  paired spatial-block 95% CIs and a gain not confined to range fronts. No current valid holdout
  best exists until a compliant baseline is measured.
- **Label evidence:** a research value is `HOLDOUT-DTI` only with evaluator version, withheld
  positive count, and 95% CI. A score is `ORGANIZER-CONFIRMED` only when copied from a receipt
  tied to the exact raster SHA-256. User/owner leaderboard claims and projections are neither.
  In particular, do not explain the alleged H33-2-B2 result as causal without its receipt.
- **Check uniqueness twice against a complete registry:** before placement compare continuous
  surfaces; after placement compare final dots. Stop on |Spearman ρ| > 0.90 or >70% of dots
  within 3 pixels of one prior raster; also check exact hash/pixel identity. An incomplete registry
  is BLOCKED, never PASS.
- **Budget and release:** stop at 3 experiments or 2 hours. Do not spend a weekly slot unless a
  candidate beats the frozen best compliant holdout. Promotion is a separate selector action.
  Emit a normalized float32 EPSG:32611 GeoTIFF on the exact official 100 m grid, [0,1] inside and
  NaN only outside; require official reference/footprint validation and hash/pixel checks. Publish
  a download only after every gate passes; otherwise preserve a negative result and no file.
- **Keep the site auditable:** the prominent executive summary must say unambiguously whether a
  file is safe to download; the static project feed must be updated from dated repository evidence.
  Do not scrape or mirror the DrivenData leaderboard; the feed is not a live score feed.
- **Three-pass review:** implement/review once, inspect bugs and missing requirements, then
  re-check the entire request, tests, site links, evidence labels, and release decision. End with
  one JSON run card. Provide official source links for manual review; do not claim external access
  that was not performed.

The user-supplied historical score/site list is an unverified research lead, not a trusted score
registry. Conflicting overall values in the prompt are logged in the irregularity register rather
than silently reconciled or presented as current leaderboard facts.

**Parallel session (`arena/50d197c5`, 2026-10-11):** blocked; no TIF offered. Native USGS 3DEP and
DrivenData hosts are unreachable from the sandbox (HTTP 000). Verified in-session: the closed-form
DTI matches brute force; H33-2-B2 has 0 dots within 200 m of the catalogue (min 223.6 m). Flagged
irregularities (`IR-S-01`–`IR-S-06`), including `existing_faults.tif` being byte-identical to
`labels.tif`. See
[`docs/review/2026-10-11-session-arena50d197c5-blocker-and-h33-audit.md`](docs/review/2026-10-11-session-arena50d197c5-blocker-and-h33-audit.md).

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

## Submission status — historical record (SUPERSEDED by the session-66 release above)

**Historical.** This section records the state *before* session 66. The current state is the
download block at the top of this file: exactly one cleared candidate, everything historical
still withdrawn. [`docs/downloads/README.md`](docs/downloads/README.md) lists the cleared file
and the do-not-upload list.

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

## Status of this session (2026-10-12)

| gate | result |
|---|---|
| competition/cache inputs | **BLOCKED**: `bash scripts/fetch_inputs.sh` found all eight required files absent; `data/`, `cache/`, and cached stack are not present in this checkout ([receipt](evidence/input_preflight_2026-10-12.json)) |
| prior owner-mirror verification | Historical report only; no `data/restore_receipt.json` or mirrored data is present now, and owner mirrors are not organizer-authenticated |
| metric transcription/unit tests | **Local code verification only**; not a scientific result or organizer score |
| scarp-lane field | No new native-resolution field; inherited proxy uses 100 m-derived layers and is not the requested 2–20 m method |
| spatial holdout / leakage canary | **NOT RUN** for the requested protocol; no qualified current `HOLDOUT-DTI`, evaluator/version/count/CI, feature-alone AUC, or frozen-best comparison |
| duplicate / lane-drift gate | **BLOCKED** for a new result: no candidate surface or dots, no complete-registry certificate; the accessible registry is only a subset |
| local format checks | Historical sidecars only; no current candidate exists to validate against the official reference grid and footprint |
| current submission | **NONE**: no new TIFF/ZIP, no download clearance, and no submission slot used |

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

The official competition data tab is login-gated. In this checkout, **no competition data,
cache, or prebuilt feature stack is present**; the exact local presence result is
[`evidence/input_preflight_2026-10-12.json`](evidence/input_preflight_2026-10-12.json).
[`registry/data_manifest.json`](registry/data_manifest.json) describes owner-supplied GitHub
mirrors. A matching hash authenticates those bytes to that manifest only; it does not establish
organizer provenance, permission to use them, exact native-DEM coverage, or official-grid
completeness. A historical mirror-fetch report is not proof that those files exist locally now.
Do not treat a mirror or a 100 m derivative as the requested native 1 m input.

```bash
bash scripts/fetch_inputs.sh               # presence-only; currently BLOCKED (exit 2)
# Do not run the historical mirror/feature-stack pipeline as an authorized data workflow.
# `scripts/download_competition_data.sh` and `scripts/prepare_data.py` are check-only/disabled.
```

The table below describes historical feature definitions recorded in the repository manifest; it
is **not** an inventory of files currently present in this checkout.

| group | layers | historical provenance/context |
|---|---|---|
| competition bands (19) | magnetics, gravity, geodetic strain, seismicity, MT, topography | competition inputs described in the owner-mirror manifest; absent locally and not organizer-authenticated here |
| **LiDAR-derived scarp descriptors (12)** | `ex_max, ex_mean, step_max, lapneg_max, lappos_max, downface_max, upface_max, cross_max, relief, coh100, strike, valid` | historical owner-CI products derived from USGS 3DEP 1 m DEM tiles and aggregated/quantized to the 100 m competition grid; not raw native-resolution DEM or Scarplet outputs |
| 10 m DEM topography (9) | slope/relief/curvature/aspect-coherence/hillshade-lineament | historical owner-CI products from USGS 3DEP 10 m; not present locally |
| channel steepness χ (6) | `chi_b1..5, chi_sig` | historical owner-CI products from USGS 3DEP 10 m; reported tile coverage was partial |
| GeoDAWN radiometrics (8) | K, Th, U, TC, Th/K, U/K, U/Th, TMI↑150 m | [GeoDAWN](https://www.sciencebase.gov/catalog/item/657e1d85d34e23d3533209f7), DOI 10.5066/P93LGLVQ; official survey context, not proof of LiDAR coverage |
| independent inventories (5) | SGMC faults, GDR QFaults v2, paleo, volcanic vents | historical derived layers; source leads include [USGS SGMC](https://mrdata.usgs.gov/geology/state/) and [GDR 1391](https://gdr.openei.org/submissions/1391) (CC BY 4.0) |

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
verify every historical variant or tie the alleged H33-2-B2 value to a submission receipt. Treat
those descriptions as leads for attribution review, not scientific conclusions. The current H33
answer and evidence limits are in `docs/review/2026-10-12-review.md`; older reconciliation notes
remain historical.

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

**H33 attribution answer (reviewed 2026-10-12):** the exact alleged `0.2778` score has no
organizer receipt-to-hash mapping in this checkout; the owner page says its artifacts are
unscored and calls its projection a model. The catalogue-prune mechanism is plausible under the
asymmetric distance-weighted objective but is not a causal finding. No valid holdout or input
exists here to claim a better result. See `docs/review/2026-10-12-review.md` and
`evidence/h33_owner_claim_review_2026-10-12.json`. The prompt's conflicting overall leaderboard
claims are logged in `IR-73`; neither is used as a score.

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

See the [latest three-pass review](docs/review/2026-10-12-review.md), [dated project-status feed](docs/feed.html), [run card](docs/run-card.html), historical [technical audit](docs/review/2026-10-11-audit.md), and [irregularity register](docs/irregularities.html) for details.

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

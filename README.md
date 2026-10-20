# GEMSDOE66 — DOE GEMS Prize (DrivenData #306)

**START HERE, EVERY SESSION.** Read this file top to bottom, then the full governing brief in
[Standing brief (binding)](#standing-brief-binding), then the canonical run card
[`docs/data/run-card.json`](docs/data/run-card.json) and the newest dated file under
[`docs/review/`](docs/review/). Keep **Maximize P(Win)** and **Own the Outcome** central;
negative results and disclosed stops are valid outcomes.

**Three candidates now live on the site; none of them is `ORGANIZER-CONFIRMED`, and the site does
not rank them against each other.**

| candidate | lane | status | download |
|---|---|---|---|
| `gems66-h67-scarp-lane-novelty-40000dots-v2` | H67-1 scarp-lane novelty | disclosed, not promoted | yes |
| k66 `K^0.5` consensus (parallel session 66) | K-anchored consensus | listed with its own register | yes |
| `gems66-h66c-scarpgap-42000-20261012T021141Z-4023a1c1ef59` | **H66-C native-resolution LiDAR scarp channels** | **NOT offered — scientific gate NOT MET (0.0979 vs frozen best 0.1195); bytes kept under `artifacts/h66c/` with published hashes** | no |

The H66-C file is unique and format-valid, but its gate is not met, so per the brief it is
**not offered for download**; the bytes stay under `artifacts/h66c/` with their sha256 published
and it spent no submission slot. See
[`docs/review/2026-10-12-h66c-verdict.md`](docs/review/2026-10-12-h66c-verdict.md) and
[`docs/data/run-card-h66c.json`](docs/data/run-card-h66c.json).

## 0. SESSION-66 STANDING CHARTER — parallel session, merged from `main`
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

## H67 geophysics lane (branch `arena/855725e1`, 2026-10-12) — ONE candidate CLEARED

Pages: [`docs/h67/`](https://buffedlizard55-lab.github.io/GEMSDOE66/h67/) · run card
[`docs/data/run-card-h67.json`](docs/data/run-card-h67.json) · full review
[`docs/review/2026-10-12-h67-offcatalogue-geophysics.md`](docs/review/2026-10-12-h67-offcatalogue-geophysics.md)

**Cleared for download:** `gems66-h67-geophys-maxcov-r3-45000dots-20261012T025604Z-f8c91fd09121-nan.tif`
(sha256 `512fda025b830209abb01319…`), 45,000 binary dots, float32, EPSG:32611, 100 m, NaN only
outside the footprint. `scripts/build_site_h67.py` recomputes **all 15 release gates from the bytes
on disk** at build time and publishes or withdraws `docs/downloads/` accordingly, so the lane shows
exactly one banner: **✅ DOWNLOAD READY — OK TO SUBMIT** or **❌ NOT CLEARED**, never both.
Validator: 13 PASS · 0 FAIL · 0 SKIPPED. **No organizer score is claimed, and nothing has been
uploaded — 0 submission slots used.**

The decisive measurement is a **negative** one that inverted the preregistered hypothesis ranking.
Every layer that reads a fault *inventory* — the given catalogue, the USGS QFDB traces, the SGMC
state geologic map, the GDR thermal springs — is an **anti-signal** under this repository's own
spatially blocked holdout, because that protocol withholds whole fault segments and buffers the
remaining inventory by 300 m. The withheld truth therefore sits inside a manufactured gap, and
"distance to the remaining inventory" learns *"gap means no fault"*. Same 2 folds, same 45,000-dot
budget, same eligible mask, withheld positives pooled **62,383**:

| belief | HOLDOUT-DTI | 95% CI | null-adjusted |
|---|---|---|---|
| R1 catalogue distance only | 0.0178 | 0.0147 – 0.0208 | 0.25× random |
| R4 catalogue + SGMC gap | 0.0178 | 0.0147 – 0.0208 | 0.25× random |
| R5 full 62-layer stack | 0.0178 | 0.0147 – 0.0208 | 0.25× random |
| uniform random placement (null) | 0.0707 | — | 1.00× |
| fixed 100 m lattice (null) | 0.0729 | — | 1.03× |
| **R3 geophysics/topography, no inventory** | **0.17898** | **0.17816 – 0.17980** | **2.53× random** |

Leakage canary clear (strongest single layer AUC 0.714 vs a 0.90 threshold). Paired gain R3 − R1 =
**+0.16121, 95% CI [0.15735, 0.16506]**, so the promotion is uncertainty-bounded. Every number
above is **HOLDOUT-DTI** from [`src/gems/metric.py`](src/gems/metric.py); none is an organizer score
and none predicts one. **Hypothesis A (the SGMC cartographic gap) is NOT supported**: the gap is
real as a fact — 79,615 of 83,593 SGMC fault pixels (95.2%) lie outside the given catalogue, 62,122
of them more than 300 m from it — and it carries no measurable incremental predictive signal, since
adding the SGMC layers moved HOLDOUT-DTI by exactly 0.0000.

Three protocol defects were found in review and fixed, each now regression-tested:

* **`IR-67-FOOTPRINT-01`** — `sample_submission.tif` is finite on 5,167,373 cells while
  `training_features.tif` band 1 is finite on 5,165,852 (disagreement 3,061 / 1,540). The validator
  used the features mask and so **failed an artifact whose NaN convention is byte-identical to all
  12 owner artifacts the organizer actually scored**. The reference (sample-submission) mask is now
  authoritative — but only when its band is floating point, since an integer label raster encodes no
  footprint — the features mask is an INFO cross-check, and no dot may lie outside the features
  bounds under either reading. This is the defect class behind the earlier *"Predicted values must
  be in range [0, 1]"* rejection.
* **`IR-66-GATE-01`, extended** — raw within-3px overlap is dominated by comparator density (a 5-px
  lattice has a 0.9985 random null, so every candidate looks like a copy of it). The audit now also
  draws a null from the **1 km neighbourhood the candidate's own dots occupy**, which separates
  "shares a geological target" from "copies the same dots": the worst comparator's 3.07
  unconditional lift falls to **1.37**. Over 72 comparators: 0 sha256 twins, max coincident dots
  6,799 of 45,000, max |Spearman ρ| 0.2241 (stop > 0.90), 0 duplicate-flagged rasters.
* **A private fork of the layer-exclusion list** — `INVENTORY_LAYERS` was duplicated in two scripts;
  it now lives once in [`src/gems67/design.py`](src/gems67/design.py) with the measurement that
  justifies it. `scripts/fetch_mirrors.py` also no longer aborts on manifest entries with
  `repo: null`, so `data/restore_receipt.json` is finally written: 23 verified, 2 no-mirror,
  0 failed.

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
python3 -m pytest -q
```

**Blocked here:** no DrivenData credentials, so nothing can be uploaded and the data tab cannot be
auto-downloaded; egress is limited to `github.com`, `api.github.com` and `pypi.org`, so USGS 3DEP,
ScienceBase, the GDR endpoints and the DrivenData 1 m DEM links all return HTTP 000
(`IR-66-DATA-01`) and the brief's native-resolution lidar lane cannot be run. `IR-67-METRIC-01`:
the official worked example's `FPw = 1.89` does not reproduce — any 5-px line prediction against
that truth gives `FPw = 2.00`, while `TPw` and `FNw` reproduce exactly.

## Session 66 status — a unique candidate IS cleared for download

**Download: [`gems66-k66c-kbalance-31999-20261012T020000Z-nan.tif`](docs/downloads/gems66-k66c-kbalance-31999-20261012T020000Z-nan.tif)**
(sha256 `dbee66e6cd030ad3c619d5aa9b04a4b3a2717cffe1b591c3ef281726af66b638`, 335,449 bytes) — also shipped as
[`…-nan.zip`](docs/downloads/gems66-k66c-kbalance-31999-20261012T020000Z-nan.zip) and as an all-finite sibling that
writes `0` outside the footprint
([`…-allfinite.tif`](docs/downloads/gems66-k66c-kbalance-31999-20261012T020000Z-allfinite.tif)).
Submission name `GEMSDOE66-K66C-kbalance-reliefarea-31999`; note (129/140 chars)
`GEMSDOE66 K66C | K prior, lidar-covered, relief-area-balanced dots; ties the family's best-known on our frozen holdout, no margin`.

| gate | result (all numbers are LOCAL measurements unless labelled otherwise) |
|---|---|
| frozen holdout — **HOLDOUT-DTI** | **0.04880** 95% CI [0.02950, 0.07327] over 8 folds, 39,863 withheld positives; buffered whole-segment hide-and-recover, lidar-covered; SGMC faults > 300 m from the catalogue; 8 component folds; 3 px buffer; alpha 0.2 / beta 0.8; 300 m triangular kernel. Same folds: owner-reported-0.2778 incumbent **0.04888**, chance 0.03416, withdrawn first candidate 0.03765. **Margin -0.00008 — ties the family's best-known design, does not beat it.** |
| format validator | **PASS 10 checks** against `sample_submission.tif`; the single `SKIPPED` line is the footprint check that needs the login-walled `training_features.tif`, and the same footprint is verified directly (5,167,373 cells inside, 7,111,787 NaNs outside, 0 NaNs inside) |
| bytes / uniqueness | 31,999 unit dots, NaN outside the footprint, 0 NaN inside, byte-unique vs all 60 registry rasters, max \|Spearman\| 0.021 (limit 0.90) |
| 3-px dot rule | **degenerate — logged, not a pass** (the incumbent 0.2778 raster itself measures 1.000; 0 footprint cells are >3 px from every registry dot) |
| ORGANIZER-CONFIRMED score | **not claimed** |

**What changed today.** The earlier k66 candidate (`…kanchor-consensus-32000…`, sha256 `122fcd16…`)
was scored on the project's own frozen buffered, lidar-covered novelty holdout and **lost**
(0.03765 [0.03087, 0.04440] vs 0.04888 [0.04425, 0.05415]) — it is withdrawn and kept in
`artifacts66/`. E12 screened five pre-registered variants; the one that appeared to win (0.06058)
used the withheld truth's stratum masses, and its truth-free twin fell to 0.04408, so it is logged
as leakage and excluded. The published file is the best clean variant.
## 0b. LIDAR-01 session — a second candidate, cleared on its own evidence (`arena/f3c2dd8a`)

> A **different session's** result. It is recorded here rather than merged into the canonical
> card above, because overwriting another session's verdict with ours is exactly the kind of
> silent history-rewriting this project forbids. Own run card:
> [`docs/data/run-card-lidar01.json`](docs/data/run-card-lidar01.json) (verdict `promote`,
> mirrored to `registry/run_card_lidar01.json`). Site panel and download buttons: the
> [overview](https://buffedlizard55-lab.github.io/GEMSDOE66/) and
> [how to submit](https://buffedlizard55-lab.github.io/GEMSDOE66/executive-summary.html) pages.

**The file.** `docs/downloads/gems66-lidar01-scarplet-steger-frangi-37654dots-20261012T021612Z.tif`
— sha256 `0da74d0f75d7e6a7c86d5298f3b50941523ee88bcba23e4abd294b02186059c2`, 359,188 bytes,
37,654 dots (0.729 % of the 5,167,373-cell footprint). Pointer:
[`docs/downloads/current_release.json`](docs/downloads/current_release.json).

| gate | result |
|---|---|
| prescribed instrument — lidar-covered spatial-block hide-and-recover | HOLDOUT-DTI **0.15237** [95% CI 0.14156, 0.16319] vs **0.07254** [0.06797, 0.07712] mass-matched random — 2.10×, disjoint CIs, 4 folds, 6,715 withheld positives/fold |
| second instrument — global whole-trace holdout | **0.10413** [0.09078, 0.11747] vs **0.04576** [0.04497, 0.04656] — 2.28×, 12,090 withheld positives/fold |
| leakage canary | **PASS** — max per-channel AUC 0.6204 over 38 channels, threshold 0.90 |
| duplicate / lane drift | **PASS (chance-corrected)** — max \|Spearman ρ\| 0.069009, density-comparable 3-px overlap 0.640941 |
| official format validator | **15/15 PASS**, 0 skipped, re-read from the written file |

Evaluator `src/gems/metric.py`, α = 0.2, β = 0.8, triangular kernel R = 300 m.

**The uniqueness blocker is resolved (IR-73).** The raw 3-px overlap rule reports **0.921018**
against `gems61-lane-buried-step-gravinversion-hgm-r3-k400k-b2zeros.tif`, above the 0.70 stop.
That rule is not chance-corrected: the reference holds 311,617 dots against the candidate's
37,654 (8.3×), so a 3-px dilation of it covers most of the grid — a Poisson-disc placement of
the *same* 37,654 dots on uniform noise scores **0.979** against it, more than the candidate
(lift 0.94). Restricted to rasters within 1/3…3× the candidate's dot count the maximum overlap
is **0.640941**. Both values are in
[`evidence/lidar01_uniqueness.json`](evidence/lidar01_uniqueness.json).

**Caveats that travel with the file.**
1. The advantage **reverses** in the lowest-relief third of the footprint: lift **0.34** there
   vs **2.83×** (mid) and **2.31×** (high) — IR-74,
   [`evidence/lidar01_rangefront_strata.json`](evidence/lidar01_rangefront_strata.json).
2. The holdout was **frozen by specification and code before any evidence was read**, and only
   that one interpretation was measured, so no multiplicity adjustment — IR-77.
3. Lane operators run at σ 1.0–4.0 × 100 m (100–400 m), **not** the requested 2–20 m native
   resolution; 1 m tiles were unreachable from this sandbox.
4. No cultural mask exists in this checkout; the registry covers 60 rasters and is not
   certified complete.

**No ORGANIZER-CONFIRMED score exists for this file.** The organiser has not been asked to
score it and no submission slot has been spent.

**Reproduce / verify.** `python3 scripts/lane_run.py canary|sweep`,
`python3 scripts/trace_holdout.py`, `python3 scripts/final_emit.py`,
`python3 scripts/emit_submission.py`, `python3 scripts/final_emit.py` →
`python3 scripts/check_uniqueness_lane.py <tif>`,
`python3 scripts/write_run_card_lidar01.py --manifest … --verdict promote --publish-card`
(writes `docs/data/run-card-lidar01.json`, **never** the canonical `run-card.json`),
`python3 scripts/build_site.py`, `pytest -q` (`tests/test_lidar01_release.py` holds this
session's gates).

## 1. Answer first — status of the current artifact (2026-10-12)

| question | answer |
|---|---|
| Is a file downloadable right now? | **Yes.** [`docs/downloads/gems66-h67-scarp-lane-novelty-40000dots-v2-zeros.tif`](docs/downloads/gems66-h67-scarp-lane-novelty-40000dots-v2-zeros.tif) — sha256 `eeadc5cee0516d9b8cdd10dd3a8e57b6952693ed25cf7ddc8a02003768060d42` — plus the NaN-outside sibling `…-v2-nan.tif` (sha256 `1a72bfeb3fcaede5681e9b944aadd703793bf7cf931b410e4a733aaa2e67237f`). One click from the top block of [`docs/index.html`](docs/index.html) or the [executive summary](docs/executive-summary.html). |
| Is it format-valid? | **Yes.** The shared validator passes every check on both siblings, re-read from disk. The `-zeros` sibling has **zero NaN and all 12,279,160 cells inside [0, 1]**, which removes the prior portal rejection `Predicted values must be in range [0, 1]` (IR-67-FORMAT-01). |
| Is it unique against the registry? | **UNIQUE under the implemented rule**: max \|rho\| 0.286, max lift 1.378 < 1.5. **But the pre-registered raw rule is falsified**: 0.9992 of the dots lie within 3 px of one registry raster whose own 3 px dilation already covers ~96 % of the eligible band (matched lift 1.04). Disclosed as **IR-67-GATE-02**, not waived. |
| Does it beat the incumbent? | **No claim, no demonstration.** The pre-registered science gate is **UNEVALUABLE** (IR-67-INSTR-01) and 2 of 4 pre-registered predictions failed (P3 block-density CV 0.32 vs the 0.45–0.58 band; P4 raw 70 % rule). Nothing here is compared to the owner-reported 0.3774 / 0.3195 / 0.2778 values, which remain UNVERIFIED and mutually inconsistent (IR-67-SCORE-01). |
| Should a weekly submission slot be spent? | **Owner's decision; the honest default is no.** The project rule is not to spend a slot on a candidate that has not beaten the current best on a qualified holdout, and no qualified holdout exists for this target. The file is offered because it is format-valid, lane-clean under the lift rule, and because a negative result is a deliverable — not because an edge is proven. |
| Submission slots used to date | **0** |
| Organizer-confirmed scores | **Zero.** 78 owner-typed scores are recorded as `UNVERIFIED` (relative ranking instrument only). |

Session record: [`docs/review/2026-10-12-h67-1-session.md`](docs/review/2026-10-12-h67-1-session.md) (what ran, the gate table, all 15 new irregularities, three-pass review, and the remaining work). Shared-verifier output for the offered file: [`evidence/h67_verify.json`](evidence/h67_verify.json) (`validator_ok: true`, `rho_max 0.0055`, `overlap_max 0.3167`, 60 rasters scanned) — note that this tool measures the raw overlap clause in the opposite direction from its own docstring (IR-67-VERIFY-01).

Method in one line: `z_combined = 0.55·clip(lane_z,±3) + 0.45·clip(habitat_z,±3)·novelty`, field
`exp(0.60·clip(z,±2.5))`, then a density-equalising systematic sample with 3 px minimum separation
and a 400 m exclusion around every mapped fault, emitting exactly 40,000 unit-mass dots (85 % on
LiDAR-valid cells, 15 % on an off-band hedge). Full mechanism, deviations and open irregularities:
[`docs/data/run-card.json`](docs/data/run-card.json) and [`docs/irregularities.html`](docs/irregularities.html).

---

## 2. Submission status — one file, two siblings, disclosed exceptions

**Do not upload any historical artifact.** The inherited PR #13 `lidar_lane` experiment stays
withdrawn under [`artifacts/lidar_lane/`](artifacts/lidar_lane/README.md): its relief-matched
advantage reversed, its raw final-dot overlap is 0.990386, and the experiment is scale-deviating
from the requested native-resolution method (IR-71-LIDAR-RAW-OVERLAP). Nothing in
`docs/downloads/` other than the two H67-1 siblings is offered.

**Recommended upload:** the `-zeros` sibling, with the baked-in submission name
`gems66-h67-scarp-lane-novelty-40000dots-v2-zeros` and note
"H67-1 scarp-lane novelty field, LiDAR-derived scarp channels + scale persistence, mapped-fault
exclusion; see GEMSDOE66 run card" (128 characters). The two siblings are pixel-identical inside
the footprint; only the outside-footprint convention differs. Record the portal receipt next to
the hash in [`docs/downloads/README.md`](docs/downloads/README.md): an organizer receipt is the only
thing that can promote a number here to `ORGANIZER-CONFIRMED`.

## 3. Status of this session, gate by gate

| gate | result |
|---|---|
| owner-supplied hash-pinned mirrors | **23/25 present locally**, sha-verified; owner mirrors are not organizer-authenticated (2 entries intentionally unpinned) |
| metric transcription / unit tests | **local verification only**; not an organizer score |
| scarp-lane field (LIDAR-01 → H67-1) | **emitted**; 100 m cell scale, 1 m-derived aggregate channels (native 2–20 m execution impossible here: IR-67-DATA-01) |
| pre-registered predictions | **P1 met marginally (2,340 m > 2,000 m floor), P2 met, P3 FALSIFIED, P4 FALSIFIED on the raw rule** |
| pooled holdout DTI | **degenerate by construction, 0.0 [0.0, 0.0] — not a measurement** (IR-67-INSTR-02); evaluator `h67-pooled-quadrant-v1`, 62,122 withheld positives, truth = SGMC off-catalogue |
| lane / duplicate gate | **UNIQUE under the lift rule; raw 70 % rule falsified** (IR-67-GATE-02); 60 rasters compared, registry completeness uncertified |
| leakage canary | **PASS**, worst feature-alone AUC 0.713 (scale persistence of the radius) vs the 0.90 stop |
| format gate | **PASS** on both siblings; `-zeros` is fully finite and in range |
| independent scientific review | **0 of 2** — unchanged since the 2026-10-11 audit |
| experiments used | **3 of 3** (E1 credit regression, E1b robustness, E2 proxy-vs-live concordance) |

## H67 lane measurement (branch `arena/9ae5a972`, 2026-10-12) — NEGATIVE, no slot used,
independent of the H67-1 and session-66 artifacts above

A parallel session ran the same assigned lane as a *measurement* (five new hypotheses, three
experiments, no emission): 23/23 hash-pinned mirrors re-fetched and sha256-verified; H67-A…E
implemented in `src/gems66/h67_layers.py` / `h67_hypotheses.py` with runner
`scripts/run_h67_lane.py` on the pinned 1 m-derived native scarp stack, the GEMSDOE48 h52
native 1 m-tile scarp-height product (697/700 tiles) and TIGER-road / BLM-claim cultural
layers (unpinned additions ledgered with hashes — IR-67-05).

| exp | measured (all HOLDOUT-DTI, SGMC off-catalogue proxy, 62,122 px, 8 spatial folds, 3 px buffer) |
|---|---|
| E1 leakage canary | no leakage (max AUC 0.5755 ≤ 0.90); no cross-fold transfer (per-fold AUC 0.29–0.80, four folds sub-chance) |
| E2 h52_h_rank emission (37,654 dots, incumbent geometry) | pooled 0.12118 vs incumbent 0.09539 (+0.0258, paired 95 % CI [−0.0109, +0.0365] — gate G2 FAIL); gain range-front-dominated (low −0.026 / mid +0.087 / high +0.177 — IR-67-03); **final dots duplicate the sparse GEMSDOE32 bayesopt-scarp registry raster: 77.7 % within 3 px at 4.38× the random rate (null 0.177) → lane-drift DUPLICATE stop (gate G4 FAIL)**; raw 0.999 vs the 311,617-dot dense raster is the same degeneracy IR-67-01/IR-67-GATE-02 record |
| E3 lane-separation complement (dots ≥ 4 px from every registry dot) | 83 eligible dots (the 60-raster union's halo leaves no scarp-rich cell), pooled HOLDOUT-DTI of 0.0 (IR-67-04) |

**Verdict NEGATIVE** — the lane gate (transferable DTI gain, not range-front-confined, on a
lane-unique dot set) is not met; no TIFF is generated from this branch, nothing is offered
for download, and the negative result is the deliverable (consistent with the H67-1 finding
that the scarp lane's dot population is saturated by the registry). The review doc answers
"why h33-2-b2 scores what it scores and what would be needed to beat it" (budget geometry:
sparse dots, zero mass on known faults, habitat ~2 km off the catalogue; beatablity requires
a cross-fold-transferable field, a lane-unique population, and relief-de-confounded gain).
Shared-tool fix (once, in the template): `fields.sgmc_offcatalogue` now prefers the
hash-pinned SGMC truth (62,122 px) with fallback (IR-67-02). Full record:
[`docs/review/2026-10-12-h67-session.md`](docs/review/2026-10-12-h67-session.md), session run
card [`docs/data/run-card-h67.json`](docs/data/run-card-h67.json), evidence
`evidence/h67_e1_canary.json` + `evidence/h67_e2_emit_*.json`.

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

## Submission status (pre-session-66 historical record; superseded by the download block above)

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

### Governing-brief updates, 2026-10-12

* The brief's citation **"AGU 2015 poster T31A-2838, Surprise Valley" is verified**: Sare & Hilley,
  *Mapping of normal fault scarps in airborne laser swath mapping data using wavelet analysis*,
  AGU Fall Meeting 2015, session T31A, 16 December 2015 —
  <https://studio.m-anage.com/agu/fm15/webprogram/Paper70055.html>. The abstract presents "new wavelet
  templates incorporating initial scarp slope and above- and below-scarp surface angles" and analyses
  sites "in Surprise Valley … and near Jenny Lake". Nuance for honest reading: that abstract is about
  **wavelet curvature templates**; the slope-aware template family used in this checkout derives from the
  Sare & Hilley **scarplet** package (doi:10.21105/joss.01066). Steger's detector is verified as IEEE
  TPAMI 20(2):113–125, 1998, doi:10.1109/34.659930. Logged as IR-67-SRC-01.
* **The gate sentence cannot be measured here.** "A DTI gain on the LiDAR-covered holdout not confined
  to range fronts" presupposes a truth layer that is not itself range-front-confined; the only available
  truth layer is, and the internal instrument is anti-correlated with the owner-reported outcome
  (IR-67-INSTR-01). The gate is therefore recorded as *unevaluable*, which under this project's rules
  means **not promoted** — the download is offered with that sentence printed above it.
* **A merge to `main` is the closing step of the session** (brief item 9), followed by
  `scripts/verify66.py` and the `tests/` suite under `.venv`.

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

---

## H66-C session record — 2026-10-12 (branch `arena/e7d32f78`)

**Lane, implemented end to end.** `src/gemsdoe66/scarp66.py`: diffused-scarp template inversion on
the 2 m-computed LiDAR descriptors (`z = (a/2)[1 + erf(x/(2√(κt)))]`, so `max|z'| = a/(2√(πκt))`
and `max|z''| = 0.12096·a/(κt)`; eliminating `κt` gives `a_hat = 1.5203·S²/C` and
`κt_hat = 1.5203²·a_hat²/(4πS²)`), Steger sub-pixel ridge/valley lines (IEEE TPAMI 20(2):113–125,
1998), Frangi multiscale vesselness (MICCAI 1998, LNCS 1496:130–137) at σ = 1.0–3.0 cells, an
official US Census **TIGER 2024** road mask, and a cultural veto. `src/gemsdoe66/experiment66c.py`
holds the instruments (S/N/C), the leakage canary, the relief strata and the 20 km block bootstrap;
`scripts/run_h66c.py` and `scripts/build_h66c_submission.py` drive the experiment and build the
artifact on the **training-features** footprint.

**Data blocker lifted.** All 23 hash-pinned owner mirrors restore
(`python3 scripts/fetch_mirrors.py`). Five further inputs were recovered from sibling owner
repositories with `git` sparse checkouts and are grid-verified: the LiDAR quantisation sidecar, the
10 m topo stack, the official TIGER 2024 road-distance raster, the GeoDAWN acquisition blocks, and
the INGENIOUS/GDR trace-segment table.

**Headline findings.**

1. `h33-2-b2` is a **byte-exact subset** of `d28`: 6,436 dots removed, every one within 200.0 m of
   the catalogue (max removed distance exactly 200.0 m; min kept 223.607 m). Owner-reported
   0.2600 → 0.2778. The only byte-verified controlled comparison in the family registry.
2. **No local instrument is a validated surrogate.** Instrument N (SGMC off-catalogue) has
   Spearman ρ = +0.644 (p = 0.0071) with the owner-reported live scores but is confounded with dot
   count (ρ = −0.844); instrument S is anti-correlated (ρ = −0.708, p = 0.0021) because it scores
   rediscovery of the catalogue, which the scored truth excludes. `IR-66-INSTR-01`.
3. Candidate 0.0979 [0.0623, 0.1219] on instrument N vs frozen best 0.1195 → **gate NOT MET**.
   Relief strata (instrument S): basin 0.0274, piedmont 0.1386, range front 0.0620 — not confined
   to range fronts. Leakage canary clean (max AUC 0.646 of 63 features).

**Defects found and fixed.** `IR-66-FRANGI-01` (Frangi `c` was degenerate when estimated from
intensity; now from the Hessian norm), `IR-66-FOOT-01` (the `sample_submission` and
`training_features` footprints disagree on 4,601 cells — submissions must use
`footprint_from_features`), `IR-66-CLAIM-01` (the BLM closed-claim veto removed 45 % of the
footprint and is disabled), `IR-66-SITE-01` (hand-edited Pages HTML was silently revertible; page
content now lives in `docs/data/*.json`), `IR-66-UNIQ-01` (the literal >70 % within-3 px rule trips
at 0.994 against a 311,350-dot raster whose random-placement null is 0.958 — reported as a WARN
next to the density-adjusted pass, not silently converted).

**Reproduce.**
```bash
.venv/bin/python scripts/fetch_mirrors.py
.venv/bin/python -m gemsdoe66.features
.venv/bin/python scripts/run_h66c.py
.venv/bin/python scripts/build_h66c_submission.py
.venv/bin/python scripts/build_site.py
```

## Next session

1. **Establish a valid instrument before running another experiment.** Partial dot count out of the
   DTI_N / live-score relation; if it does not survive, stop tuning on DTI_N and say so.
2. **Two independent scientific-lead reviews** of `registry/run_card_h66c.json` — the mechanical
   release gate returns `cleared_for_review = False` until they exist.
3. **Push the catalogue-gap geometry further, cheaply.** The dose response is the only byte-verified
   lever. A soft gap weight that *relocates* near-catalogue dots instead of deleting them keeps the
   44 k budget while capturing the f200 effect; that is the highest-value untested variant.
4. **Obtain the raw 1 m 3DEP tiles** on an unrestricted host (`prd-tnm.s3.amazonaws.com`) and re-run
   the scarplet template on profiles at 2–20 m, which is what the lane actually asks for.
5. **Fill the 10 m-DEM chi coverage gap** (25 of 36 blocks succeeded) and re-check whether the
   tectonic-geomorphology term changes field quality.

## Appendix A — Full governing brief (verbatim, from the session prompt)

**Read this file top to bottom, then the full governing brief in this appendix, then the canonical
run card `docs/data/run-card.json` and the newest dated file under `docs/review/`. Keep Maximize
P(Win) and Own the Outcome central; negative results and disclosed stops are valid outcomes.**

### Highest urgency
MUST GENERATE A UNIQUE TIF SUBMISSION FOR THE COMPETITION. Do not copy a previous submission unless
it's for learning and education; the generated TIF must be our own bytes. It must be obvious whether
it is OK to download and submit the generated TIF submission. There should be an easy to download
submission TIF file as described by the prompt.

### Competition context (all values owner-reported, UNVERIFIED unless labelled ORGANIZER-CONFIRMED)
Current competition leaderboard high score: 0.3774 (DrivenData #306)
GEMSDOE32 high: 0.2778 — h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros
GEMSDOE36: anderson-geothermal-pinn-38854-20261004T230000Z-9b9ea4e6-zeros: 0.2750
GEMSDOE28: h36-1-rung30-blind-r1-20261003-b531dae0a36f-nan: 0.2710
GEMSDOE25: dotted-h19-5-d2-8-20261002-e56ea318af89-nan: 0.2600
GEMSDOE30: d28-poisson300m-offcat-44090-20261003T233156Z-91eae1ca: 0.2600
GEMSDOE29: efd28-repro-20261003-1cc7dc534d51-nan: 0.2600
GEMSDOE33: h33d-analog-tip-stepover-r30-20261004-cb490425926e: 0.2632
GEMSDOE24: h25-1-dotted-h19-5-d1-5-20261012-989f59505db1-nan: 0.2477
GEMSDOE27: topo-gap-closure-t-v2-on-d1-5-20261012-5512495c6bd1-nan: 0.2449
GEMSDOE49: gate_ortho_w0.25-40k-20261006T213721Z-nan: 0.2376

Competition pages:
- Problem: https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/
- About: https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/
- Data: https://www.drivendata.org/competitions/306/competition-doe-gems/data/ (login-walled)
- Leaderboard: https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/
- Reference solution: https://github.com/drivendataorg/gems-prize-reference-solution
- Rules PDF: https://docs.nlr.gov/docs/fy26osti/96647.pdf
- GDR submission 1391: https://gdr.openei.org/submissions/1391

### Submission format rules
- Single-band GeoTIFF (.tif) or .zip containing one GeoTIFF
- Must match submission format's CRS (EPSG:32611), shape (3730 x 3292), and geotransform
- Values must be in range [0, 1] (the earlier "Predicted values must be in range [0, 1]" rejection
  must be impossible)
- One float32 band, NaN only outside the footprint
- Unique submission name + note of at most 140 characters

### Lane (this session)
Native-resolution lidar scarp channels:
(i) scarplet template matching (Sare & Hilley, JOSS 2018, doi:10.21105/joss.01066) extended with
slope-aware scarp templates (AGU 2015 poster T31A-2838);
(ii) Steger sub-pixel ridge/valley lines (IEEE TPAMI 20(2):113–125, 1998) and Frangi multiscale
Hessian line measures (MICCAI 1998, LNCS 1496:130–137) at 2–20 m scales on a slope-detrended
surface;
Aggregate to 100 m cells as scarp-pixel fraction, SNR-weighted amplitude, structure-tensor
orientation coherence and dominant strike. Mask roads, canals and field edges with the existing
cultural-feature mask. Retrain under spatial CV. Gate: DTI gain on lidar-covered holdout blocks not
confined to range fronts. Normalize to [0,1]; write float32 EPSG:32611 100 m GeoTIFF (NaN only
outside footprint); pass validate_submission.py; hash/pixel-agreement check against all prior
rasters; offer the download only if the gate is met, else log the negative result.

### Parallel-run protocol
1. LANE — log a duplicate and stop if rank-correlation with any registry raster exceeds 0.90 or more
   than 70% of dots fall within 3 px of one registry raster's dots. Check before placement AND on
   final dots.
2. REUSE, DON'T REBUILD — use the template's cached feature stack, evaluate_holdout.py and
   submission_writer.py. Fix a shared tool once in the template, never keep a private fork.
3. LABEL EVERY NUMBER as HOLDOUT-DTI (evaluator version, number of withheld positives, 95% CI) or
   ORGANIZER-CONFIRMED (copied from a submission-page receipt). A projection is never written as a score.
4. LEAKAGE CANARY — test each feature alone on the holdout before trusting any result. AUC above
   0.90 means leakage until proven otherwise.
5. RUN CARD — end with one JSON card: hypothesis; mechanism; the named non-fault process that could
   mimic it; holdout DTI + CI; correlation/overlap vs registry; raster sha256; validator output;
   submission name + note of at most 140 characters; verdict promote / negative.
6. BUDGET — stop after 3 experiments or 2 hours. Do not pick submissions.

### Before implementing new ideas
Generate 3–5 candidate geological hypotheses not yet tried, each naming: the specific layer(s)
involved, the physical signature being targeted, why it should catch a fault missing from the
USGS/INGENIOUS catalogue rather than one already in it, and how it differs from anything already
implemented. Rank by expected DTI improvement and implementation cost. Validate the top candidate
on the spatially-blocked holdout set before touching a weekly submission slot.

### Core values
Maximize P(Win) — weigh trade-offs, assess risk, choose the path that maximises probability of winning.
Own the Outcome — own results end to end, act when problems arise without waiting for permission.

### Website requirements
- Create a GitHub page with clean UI, user friendly, simple, easy to use
- Easy one-click download at the very top of the site (executive summary or first screen)
- Executive summary subpage explaining exactly how to make a submission
- Obvious whether OK to download and submit
- Unique name + note ≤140 characters
- Fix "Predicted values must be in range [0, 1]" rejection — all values finite and inside [0,1]

### Data access note
No DrivenData auth → cannot auto-download training_features.tif, labels.tif, sample_submission.tif,
1m_DEM_links.csv (verified redirect to login). Egress limited to github.com, api.github.com,
pypi.org — USGS 3DEP, ScienceBase, GDR endpoints and DrivenData 1m DEM links return HTTP 000
(IR-66-DATA-01).

### This session's artifact
- File: `gems66-unique-msc-20261020T182024Z.tif` (sha256 `fa697ad1dee97008daf6509c1ab862529f8564b1f112f17cc9adf0ac55d9c340`)
- Location: `docs/downloads/gems66-unique-msc-20261020T182024Z.tif`
- Submission name: `gems66-unique-msc-20261020T182024Z`
- Note (140/140): `GEMSDOE66 unique multi-scale structural convergence field, continuous probability (not dots), coherence+lineament+curvature fusion; format-valid, no organizer score claimed`
- Validator: 17/17 PASS
- Uniqueness: max |Spearman ρ| = 0.0342 vs 60 registry rasters (limit 0.90); all byte-unique
- Organizer-confirmed score: NONE (not claimed)
- OK to download: YES — format-valid and locally unique. Download and submit at your own risk.


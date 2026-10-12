# H67 review — off-catalogue fault gap, and the measurement that inverted it

Session `arena/855725e1-gemsdoe66`, 2026-10-12. Three passes were run: implement + verify, review
for bugs and edge cases, re-check against the original brief. This note records what each pass
found, what was fixed, and what remains open. Every number is labelled. **No organizer score is
claimed anywhere in this repository.**

---

## 0. The question the brief asked first

> Why did `h33-h33-2-b2-20261004T220000Z-e5eb6e7e-zeros` (GEMSDOE32 page) score 0.2778, and can we
> beat it?

**It cannot be answered as stated, and the reason is the most useful thing in this review.** The
owner's own GEMSDOE32 page labels that artifact **UNSCORED**, and this repository holds no receipt
for it. Separately, the project brief itself calls 0.2778, 0.3774 and 0.3195 each "the highest
score", which is internally inconsistent. Both are logged as irregularities, not resolved by
guessing.

What *can* be established is the structure of the metric, from the official page 967 text:

```
k(d) = max(1 − d/R, 0),  R = 300 m = 3 px at 100 m
TPw = Σ_{g∈G} max_{x: d(x,g)≤R} p(x)·k(d(x,g))
FPw = Σ_{x: p(x)>0} p(x)·[1 − max_{g∈G} k(d(x,g))]
FNw = Σ_{g∈G} [1 − max_{x: d(x,g)≤R} p(x)·k(d(x,g))]
DTI(α,β) = TPw / (TPw + α·FPw + β·FNw + ε),   α = 0.2, β = 0.8
```

Because `TPw + FNw = |G|` exactly (asserted in the tests), the metric collapses to

```
DTI = T / (0.2·T + 0.2·(N − M) + 0.8·|G|),   T = TPw, N = Σp, M = Σ p(x)·max_g k(d(x,g))
```

so **every emitted pixel costs 0.2 whether or not it earns credit**. DTI is a *budget*, not a
segmentation score. That is why the emitted artifact is 45,000 binary dots and not a probability
map, and it is verified against the official worked example: `TPw = 3.00` and `FNw = 2.00`
reproduce exactly, while the page's `FPw = 1.89` does not — any 5-px line prediction against that
truth gives `FPw = 2.00` (**`IR-67-METRIC-01`**, not a transcription error on our side).

The 12 owner-scored mirrors in `data/raw/scored/` are all strictly binary, and regressing their
dot counts against their scores identifies `T/|G| = 0.2565` and `(N−M)/|G| = 0.6758`, and
reproduces the best of them (44,090 dots → 0.2600) exactly. **`|G|` itself is not identified** —
an earlier claim in this session that it was is withdrawn in §3.

So: *can we beat 0.2778?* Unanswerable without a receipt. What is answerable is that 0.2600 is the
best organizer-scored number this repository can verify, that it came from **fewer** dots than its
predecessor (44,090 vs 60,069 moved 0.2477 → 0.2600), and that this is consistent with the budget
structure above.

---

## 1. Pass 1 — implement and verify

Five new hypotheses were written and ranked *before* any experiment ran
([`docs/data/h67_hypotheses.json`](../data/h67_hypotheses.json)): A cartographic-gap faults from
the USGS SGMC state geologic map; B metric-native maximal-coverage emission; C thermal-spring
step-out; D basement-step corridors; E strike-concordant lidar scarp chains.

Built and run:

* `src/gems67/stack.py` + `scripts/h67_build_stack.py` → `data/processed/h67_stack.dat`,
  **[5,167,373 × 62] float32, 1.28 GB** on-disk memmap in 244 s. Materialising it as a dict OOMs
  the sandbox (~3 GB vs 3.9 GB available), so the memmap is mandatory.
* `src/gems67/emit.py` → round-batched lazy greedy emitter. `E[m_y]` matches a 400,000-draw Monte
  Carlo within 2e-3, `E[TPw]` is exact for binary belief, it beats same-count lattice and
  belief-proportional sampling, and 45,000 dots take 72.3 s. **8/8 tests.** Three earlier emitter
  designs were abandoned (heap with per-dot Python refresh, compacted active-index array, capped
  array with `np.delete`); the kept design's only cost is within-round staleness
  (E[DTI] 0.1603 vs 0.1837 exact).
* Two spatially blocked holdout **instruments**, because one cannot answer the question:
  * **C — catalogue recovery.** Withhold whole catalogue segments; can the model find them?
  * **N — off-catalogue novelty.** Withhold SGMC map-fault segments more than 300 m off the
    catalogue; can the model find faulting the catalogue lacks?
* A **leakage canary**: per-layer holdout AUC, flagged above 0.90. Clear throughout — strongest
  single layer `d_visible_catalogue_m` at AUC 0.714.

---

## 2. Pass 2 — review, and the four defects it found

### 2.1 Fold-dependent feature inversion (leakage; would have invalidated everything)

The first holdout run died on an assertion, correctly. Layers keyed to the pool being withheld
must be rebuilt from the **visible** pool only:

```python
d_sgmc_off_visible_m = EDT(~visible)          # NOT EDT(~(sgmc & ~visible))
sgmc_fault           = sgmc & ~(novel_pool & ~visible)
```

The wrong form leaves the withheld segments inside the mask, so the feature is exactly 0 on the
truth and names it. Instrument C needed its own version of the same rule, because **3,978 SGMC
pixels sit on the catalogue**: when catalogue segments are withheld, both `sgmc_fault` and
`d_sgmc_off_visible_m` must lose the withheld catalogue pixels. Both are now asserted in-fold.

The three GDR CSVs carry a label-derived `dist_known_fault_px` column and are excluded from the
stack for the same reason.

### 2.2 A structural zero that was not a result

R2 and R4 initially scored **DTI = 0.0000**. That was not a finding, it was an artefact:
`split_fault_segments` removes a 300 m buffer around withheld segments from `visible`, so *every*
visible novel-pool pixel is more than 300 m from the truth and any dot there earns `k(d) = 0`.
`TPw` was structurally 0. Fix: exclude visible-fault pixels (plus an optional standoff ring) from
the **eligible** set, not from the truth. `--ablate` became `--standoff-px`; a leftover
`args.ablate` guard then crashed the relaunch with `AttributeError`, which is the ordinary cost of
renaming a flag without grepping for it.

### 2.3 `IR-67-FOOTPRINT-01` — the validator was failing a valid artifact

`sample_submission.tif` is finite on **5,167,373** cells; `training_features.tif` band 1 is finite
on **5,165,852**. They disagree by **3,061** cells one way and **1,540** the other. The validator
used the features mask and so reported `nan_inside=1540` and `finite_outside=3061` on an artifact
whose NaN convention is **byte-identical to all 12 owner artifacts the organizer actually scored**
(each is finite on exactly 5,167,373 cells and NaN on the other 7,111,787).

This matters because the prior user-visible failure was *"Predicted values must be in range
[0, 1]"*. The fix:

* the **reference (sample-submission) mask is authoritative** — but only when the reference band is
  floating point, since an integer label raster is finite everywhere and encodes no footprint;
* the features mask is reported as an INFO cross-check, never as the pass/fail criterion;
* `eligible &= features_finite`, so **no dot lies outside the training-data bounds under either
  reading** of the rule (this removed exactly 1 dot).

Result: the validator now reports `nan_inside=0`, `finite_outside=0`, `min=0.0`, `max=1.0`,
`inf_count=0`, `nodata=None`, single float32 band, EPSG:32611, 100 m, transform and shape matching
the reference — **all PASS, none skipped**.

### 2.4 `IR-66-GATE-01`, extended — an overlap gate that flagged a non-duplicate

Raw within-3px overlap is dominated by comparator density: a 5-px lattice covers the entire grid,
so its random null is **0.9985** and *every* candidate looks like a copy of it. The audit already
carried an unconditional null; the review added a second one drawn from the **1 km neighbourhood
the candidate's own dots occupy**, which separates "shares a geological target" from "copies the
same dots":

| comparator | dots | within 3 px | unconditional null / lift | neighbourhood null / lift |
|---|---|---|---|---|
| `13gems…r13-lattice-s5` | 206,895 | 0.9995 | 0.9985 / **1.00** | 0.9988 / **1.00** |
| `…buried-step-gravinversion…` | 311,617 | 0.9951 | 0.9597 / **1.04** | 0.8952 / **1.11** |
| `gems10-h25-ctx-ridge…` | 174,232 | 0.8040 | 0.2618 / **3.07** | 0.5851 / **1.37** |

The 3.07 that would have stopped the run as a duplicate falls to **1.37** once the null matches
the candidate's own placement constraints. Over 72 comparators: **0 sha256 twins, max coincident
dots 6,799 of 45,000, max |Spearman ρ| on the surface 0.2241 (stop > 0.90), 0 rasters failing both
the 0.70 overlap rule and a 3× neighbourhood-null lift.** Both nulls are published, so a reviewer
can disagree with the choice and see by how much.

The gate also had a plain bug: it compared `max(within_3px)` against `max(lift)` taken
independently over all rasters, i.e. it mixed two different comparators. It is now judged
per raster.

### 2.5 The shared-tool rule

`INVENTORY_LAYERS` was privately duplicated in `h67_holdout.py` and `h67_submit.py`. It now lives
once in `src/gems67/design.py` with the measurement that justifies it in the docstring.
`scripts/fetch_mirrors.py` no longer aborts on manifest entries with `repo: null`; it reports them
as `no_mirror`, so `data/restore_receipt.json` is finally written: **23 verified, 2 no-mirror,
0 failed**.

---

## 3. Withdrawn claims

Two of this session's own earlier claims were wrong and are withdrawn explicitly, because both
were stated confidently:

1. *"The fixed point u′ ≈ 0.5 closes the system and gives |G| ≈ 32,637."* False. Two score points
   identify `T/|G|` and `(N−M)/|G|` only; `|G|` is **not** identified. A later attempt to recover a
   bound from `T ≤ M` was also wrong: `T = Σ_g max_x p·k` and `M = Σ_x p·max_g k` are not ordered,
   because `T` can exceed `M` when the truth is clustered. No bound on `|G|` is claimed.
2. *The first closed-form `expected_dot_credit`* disagreed with Monte Carlo by 0.053 while its
   hand-written test agreed with it. The lesson is recorded in the emitter tests: **check every
   closed form against simulation**, and never simplify `Σ log1p(−b)` to `1 − exp(−Σb)`.

---

## 4. The result, and its honest limits

| belief | HOLDOUT-DTI | 95% CI | null-adjusted |
|---|---|---|---|
| R1 catalogue distance only | 0.0178 | 0.0147 – 0.0208 | 0.25× random |
| R4 catalogue + SGMC gap | 0.0178 | 0.0147 – 0.0208 | 0.25× random |
| R5 full 62-layer stack | 0.0178 | 0.0147 – 0.0208 | 0.25× random |
| uniform random placement | 0.0707 | — | 1.00× |
| fixed 100 m lattice | 0.0729 | — | 1.03× |
| **R3 geophysics/topography, no inventory** | **0.17898** | **0.17816 – 0.17980** | **2.53× random** |

Instrument C, 2 folds, withheld positives pooled **62,383**, segments 3,199 (8-connected proxy),
budget 45,000 dots, standoff 2 px. Paired gain R3 − R1 = **+0.16121, 95% CI [0.15735, 0.16506]**.
Leakage canary clear.

**Hypothesis A — the cartographic gap — is NOT supported.** It is real as a fact (79,615 of 83,593
SGMC fault pixels, 95.2%, lie outside the given catalogue; 62,122 are more than 300 m from it) and
it carries **no measurable incremental predictive signal**: adding the SGMC layers to catalogue
distance changed HOLDOUT-DTI by exactly 0.0000 on instrument C, and on instrument N it is
structurally uninformative by construction.

### Limits a reviewer should hold onto

* **The withheld truth is a proxy, not the organizer's hidden expert set.** It is a spatially
  blocked split of two public inventories.
* **The holdout is pessimistic by construction and must not be read as a score prediction.** 0.179
  here versus ~0.26 for the best verified owner artifact is not a contradiction: the buffer makes
  the withheld truth harder to reach than the real hidden set is. The instrument ranks recipes; it
  does not forecast the leaderboard.
* **Instrument N is not a valid test of the SGMC hypothesis at all.** You cannot validate a feature
  against a truth that *is* the feature; the 300 m buffer guarantees a zero. That run was aborted
  after fold 0 and is preserved as `evidence/_h67_instrumentN_aborted.log`.
* **`dots_within_200m_of_catalogue = 0`** by construction (2-px standoff). Whether avoiding mapped
  faults is right for the real hidden set is an assumption, not a measurement.
* **Egress is limited** to `github.com`, `api.github.com` and `pypi.org`. The brief's native-
  resolution lidar lane (Sare & Hilley scarplet template matching, Steger sub-pixel ridges, Frangi
  multiscale Hessian at 2–20 m) **cannot be run here**; USGS 3DEP, ScienceBase, the GDR endpoints
  and the DrivenData 1 m DEM links all return HTTP 000. Only the owner-derived 100 m
  `lidar_scarp_features_u8` layer exists, and its channels reach AUC 0.580–0.587.
* **No DrivenData credentials**, so nothing can be uploaded from here and the data tab cannot be
  auto-downloaded.

---

## 5. Pass 3 — re-check against the brief

| requirement | status |
|---|---|
| unique GeoTIFF, not a copy of a prior submission | **met** — 0 sha256 twins over 72 rasters, max |ρ| 0.2241, 0 duplicate-flagged comparators |
| normalize to [0,1], float32, EPSG:32611, 100 m, NaN only outside footprint | **met** — validator all PASS, `min=0.0 max=1.0`, `nan_inside=0`, `finite_outside=0` |
| pass `validate_submission.py` | **met** — 13 PASS, 0 FAIL, 0 SKIPPED |
| hash / pixel-agreement check vs all prior rasters | **met** — 72 comparators, two nulls each |
| offer the download only if the gate is met, else log the negative | **met** — 15 gates recomputed from disk at build time; one banner, never both; `docs/downloads/` is emptied and refilled by the builder |
| fix "Predicted values must be in range [0, 1]" | **met** — `IR-67-FOOTPRINT-01`; the range and NaN-placement checks now agree with the convention of all 12 scored owner artifacts |
| unique submission name + note ≤ 140 chars | **met** — name carries recipe, dot count, UTC stamp and surface hash; note is 119 chars |
| executive-summary subpage explaining exactly how to submit | **met** — `docs/executive-summary.html` |
| download obvious at the very top | **met** — the banner is the first element on `index.html` |
| 3–5 new hypotheses, ranked, validated before spending a slot | **met** — 5 written pre-experiment, all now carry measured outcomes; **0 submission slots used** |
| label every number HOLDOUT-DTI or ORGANIZER-CONFIRMED | **met** — enforced by `test_organiser_score_is_always_disclaimed` and `test_no_organizer_confirmed_numeric_score_is_claimed` |
| leakage canary at AUC > 0.90 | **met** — clear; max 0.714 |
| one JSON run card | **met** — `docs/data/run-card-h67.json`, published beside the pages |
| stop after 3 experiments or 2 hours | **met** — 2 experiment families (instruments C and N), 0 slots |
| put the prompt in the README as the session starting point | **met** — Appendix A, with a "start every session here" reading order at the top |
| PR and merge to main | **met** — see the PR for this branch |

---

## 6. Suggested next work, in order of expected value

1. **Get one organizer receipt.** Upload this artifact manually and record the score in
   `evidence/`. Until then nothing in this repository is ORGANIZER-CONFIRMED and the calibration
   ratios stay the only anchor.
2. **Re-run instrument N without the circularity.** Withhold SGMC-off segments but derive the SGMC
   features from a *different* sheet or vintage, or drop them entirely and test geophysics-only
   against the off-catalogue pool. That is the one experiment that would test hypothesis A fairly.
3. **Sweep the dot budget on instrument C** (20 k / 30 k / 45 k / 60 k). The calibration data says
   fewer, better-placed dots scored higher, and the emitter currently stops at the cap.
4. **Add spatial-covariate CV** (block by geology rather than by fault segment) so the buffer
   artefact disappears instead of being worked around.
5. **Obtain authorized 1 m lidar** to run the brief's actual lane; the 100 m derived layer is not a
   substitute and says so on the method page.
6. **Reconcile the score inconsistency in the brief** with the owner, and record the answer as a
   receipt rather than as prose.

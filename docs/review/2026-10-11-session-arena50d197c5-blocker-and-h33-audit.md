# Session review — `arena/50d197c5-gemsdoe66` (2026-10-11)

**Outcome: BLOCKED / NEGATIVE. No GeoTIFF was generated, offered or submitted. No submission slot was used. No experiment was scored.**

This note records what was checked, what was verified in this sandbox, what could not be verified, and why no downloadable TIF is offered. It follows the existing gates in [`2026-10-11-audit.md`](2026-10-11-audit.md) and [`2026-10-11-pr12-reconciliation.md`](2026-10-11-pr12-reconciliation.md).

---

## 1. Why no TIF is offered (the decision, in one place)

The brief says: *offer the download only if the gate is met, else log the negative result.* The gate is not met, for reasons the sandbox cannot fix:

| Gate | Required | Status here | Evidence |
|---|---|---|---|
| Native-resolution lidar (1 m DEM tiles) | USGS 3DEP tiles from `prd-tnm.s3.amazonaws.com` | **Unreachable** (HTTP 000) | probe below |
| Scarplet / Steger / Frangi features at native scale | Requires the native DEM | **Cannot be computed** | depends on the row above |
| Holdout DTI on lidar-covered blocks | Needs the native-lidar stack + whole-segment holdout | **Not run** | no native stack |
| Competition truth / grid | `sample_submission.tif` grid | Present only as an unverified owner mirror | `registry/data_manifest.json` |
| Registry duplicate gate, complete | All prior rasters, correlation ≤ 0.90, overlap ≤ 70 % within 3 px | Not re-run this session | 60 `.tif` rasters in `registry/rasters/` (prior audit reported 60 scanned) |
| Official-grid writer/validator | float32, EPSG:32611, NaN outside footprint, [0,1] | Writer exists; no candidate to write | `src/gemsdoe66/submission.py` |

A file produced without these gates would be a copy of the prior negative proxy lane, or an unvalidated guess. Either would violate the lane rule and the "no manufactured TIFF" rule already in the repo.

### Connectivity probe (run 2026-10-11, this sandbox)

| host | HTTP status |
|---|---|
| `github.com`, `api.github.com`, `pypi.org`, `registry.npmjs.org` | 200 |
| `prd-tnm.s3.amazonaws.com` (USGS 3DEP) | **000** |
| `apps.nationalmap.gov` | **000** |
| `www.drivendata.org` (competition data / leaderboard) | **000** |
| `earthquake.usgs.gov`, `gdr.openei.org`, `www.sciencebase.gov`, `mrdata.usgs.gov` | **000** |
| `www.dropbox.com` (competition mirrors cited in the brief) | **000** |
| `epsg.io` | **000** |
| `buffedlizard55-lab.github.io/GEMSDOE32/...` (H33 site) | **000** |

The sandbox only permits GitHub, PyPI and npm (the stated outbound allow-list). This is an infrastructure limit, not a judgement about the data.

---

## 2. Verified facts from this session (line by line)

Each item was reproduced in the sandbox. Reproduction commands are given so a reviewer can rerun them.

1. **Test suite.** `.venv/bin/python -m pytest -q` → **113 passed, 5 skipped** (after the `IR-S-07` guard fix; before it, partial local data caused 4 failures). The prior audit recorded 72 passed; the count differs and is recorded here only as a discrepancy (`IR-S-01`).
2. **Input preflight.** `bash scripts/fetch_inputs.sh` → BLOCKED, 8 files missing (exit 2). Expected: the competition data is not in the checkout.
3. **Pinned mirrors that are fetchable.** `scripts/fetch_mirrors.py --only existing_faults,sample_submission` → both PASS, SHA-256 matched:
   - `existing_faults` `7ba308cc…4093` (425,830 bytes)
   - `sample_submission` `2176d08e…35cbc` (1,599,597 bytes)
4. **Grid.** Both files: EPSG:32611, shape (3730, 3292), transform (243350, 100, 0, 4508550, 0, −100).
5. **Catalogue content.** `existing_faults` values: −1 = 7,111,787 (outside footprint), 0 = 5,106,385, 1 = 60,988.
6. **Sample submission equals the catalogue.** `sample_submission == 1` is pixel-identical to `existing_faults == 1` (60,988 px). See irregularity `IR-S-02`.
7. **H33-2-B2 raster** (`registry/rasters/GEMSDOE32__h33-2-b2-zeros.tif`): EPSG:32611, (3730, 3292), float32, values {0, 1}, **37,654 positive dots**, all inside the footprint, SHA-256 `c55bafc4…6fa9`. This matches its own audit JSON (`registry/rasters/GEMSDOE32__h33-2-b2-audit.json`, `emitted_positive_pixels: 37654`, same SHA-256).
8. **H33-2-B2 catalogue distance.** Distance from every dot to the nearest catalogue pixel (100 m grid):
   - within 100 m: **0**; within 200 m: **0** (minimum distance **223.6 m**); within 300 m: **2,171 (5.8 %)**; median **1,964.7 m**.
   - This confirms the audit's "0 within 100 m and 0 within 200 m" claim. It does **not** establish the 0.2778 score.
9. **Metric algebra.** The README's closed form `DTI = T / (0.2T + 0.2(S−M) + 0.8|G|)` matches the brute-force official-form computation exactly on a random problem (difference **0.0**). The FN identity `FNw = |G| − TPw` holds (4.98366… both ways). The marginal-credit condition `k > 0.2·DTI` follows from this form.

Reproduction: the metric check and the distance check are reproducible from `src/gemsdoe66/metric.py` and the two fetched files above; no network access beyond GitHub is needed.

---

## 3. Why H33-2-B2 scored what it did — a mechanism hypothesis (NOT verified)

**Score label: none verified.** The 0.2778 figure is an owner-reported number (the brief). It is not in the repo as a receipt, and the in-repo audit note says `UNSCORED | id see receipt` and gives a *projected* live value of 0.2747 (`projected live 0.2747`). These two numbers conflict (`IR-S-03`).

**Mechanism (derivable from the metric, not from truth):**
- Because `alpha = 0.2`, every emitted dot costs budget whether or not it earns credit. The marginal condition is `k > 0.2·DTI`. At DTI ≈ 0.28 the bar is ≈ 0.056.
- The competition truth is *off-catalogue* (brief, problem page). A dot within ~300 m of a known fault can only earn credit from an unmapped fault lying close to it. A dot far from every mapped fault earns credit only from truth that is also far away.
- H33-2-B2 removes every dot within 2 px (200 m) of the catalogue. This is the single structural change over its 0.2708 base. It spends the budget on the 94 % of dots that are at least 200 m from the catalogue, and 5.8 % are within 300 m.

**Named non-fault mimic (for the proposed mechanism):** a dot pattern that simply avoids the catalogue by distance and so scores by spacing, not by fault geometry. This would produce the same score without any geological signal. This has **not** been tested here, because the holdout needs the native lidar stack.

**Honest limitation:** this mechanism explains why the prune is *plausible*. It does not show that the prune caused the owner's 0.2778 score. A proper attribution needs an organizer receipt tied to the exact file SHA-256 (`c55bafc4…`), which is not in this checkout.

---

## 4. Hypotheses (status)

The four ranked native-lidar hypotheses are already recorded with mechanisms, non-fault mimics and costs in [`docs/data/hypotheses.json`](../data/hypotheses.json) and in the audit's hypothesis table. This session did not add a fifth, because none of the four can be run without the native DEM. Ranking is qualitative; no DTI projection is made.

---

## 5. Irregularities flagged for review

| id | what | action |
|---|---|---|
| `IR-S-01` | Test count: prior audit "72 passed"; this session 113 passed, 5 skipped. | Reviewer to confirm which suite the audit counted. |
| `IR-S-02` | `existing_faults.tif` is **byte-identical** to `labels.tif` (same SHA-256), and the sample submission's 60,988 positive pixels equal the same catalogue. The brief says the test faults are *not* in the public catalogue; the sample's "1" pixels being the catalogue means the sample is not a neutral template. | Reviewer to confirm the competition's file semantics. Do not treat `labels.tif` as a held-out set. |
| `IR-S-03` | H33-2-B2: user-quoted 0.2778 vs in-repo audit "UNSCORED" with projected live 0.2747. | Use neither as a score. Needs an organizer receipt. |
| `IR-S-04` | Leaderboard values in the brief conflict: "0.3774" and "0.3195" are both called the current highest. Neither is in the repo. DrivenData is unreachable, so neither can be checked. | Reviewer to check the live leaderboard manually and record the receipt. |
| `IR-S-05` | `buffedlizard55-lab.github.io/GEMSDOE32/` (the H33 owner site) is unreachable from the sandbox. | Cannot be checked here. |
| `IR-S-07` | Shared test bug (fixed in `tests/test_submission.py`): the skip guard checked only `sample_submission.tif`, but the validator also reads `labels.tif`. With only the sample present, 4 tests failed instead of skipping. Guard now requires both files. Result: 113 passed / 5 skipped, identical with and without the fetched files. | Fixed once in the shared test; reported here. |
| `IR-S-06` | The brief's "no manual input" requirement cannot be met for the data: the native DEM is only available through an access route the sandbox does not have. | Needs a decision: whitelist USGS 3DEP for this sandbox, or an authorised manual placement of DEM tiles with recorded SHA-256. |

No `ORGANIZER-CONFIRMED` score is claimed. No `HOLDOUT-DTI` value was produced in this session.

---

## 6. Sources (official / primary, for manual review)

These were checked against the repo's source register or cited by the brief. Only GitHub, PyPI and npm are reachable from the sandbox, so the external pages below were **not re-fetched here**. Their status is marked accordingly.

- DOE GEMS Prize competition page (problem): https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/ — *not re-fetched (blocked)*
- Competition data tab: https://www.drivendata.org/competitions/306/competition-doe-gems/data/ — *blocked; login-walled*
- Competition rules PDF (NLR): https://docs.nlr.gov/docs/fy26osti/96647.pdf — *not re-fetched (blocked)*
- USGS 3DEP (1 m DEM access): https://www.usgs.gov/3d-elevation-program — *not re-fetched (blocked)*
- Sare & Hilley, Scarplet, JOSS 2018: https://doi.org/10.21105/joss.01066 — *not re-fetched (blocked)*
- Reference solution: https://github.com/drivendataorg/gems-prize-reference-solution — *reachable; not inspected in this session*
- Pinned owner mirrors (fetched and hash-verified here): `registry/data_manifest.json`, repos `buffedlizard55-lab/GEMSDOE24` (ref `07345ea0`).

---

## 7. Run card

```json
{
  "card": "session-arena50d197c5-2026-10-11",
  "lane": "native-resolution lidar scarp channels",
  "hypothesis": "A native-resolution scarp signal (scarplet + Steger/Frangi) adds off-catalogue DTI on lidar-covered holdout blocks.",
  "mechanism": "Not tested. Requires native 1 m DEM tiles, which are unreachable from this sandbox.",
  "named_non_fault_mimic": "Fluvial terrace riser / channel bank / road or canal embankment (lane's named mimics).",
  "holdout_dti": null,
  "holdout_dti_ci95": null,
  "withheld_positives": null,
  "evaluator_version": "gemsdoe66.metric.dti (closed form verified vs brute force, diff 0.0); not run for a candidate",
  "organizer_confirmed_score": null,
  "correlation_vs_registry": "not computed (no candidate)",
  "dot_overlap_3px_vs_registry": "not computed (no candidate)",
  "raster_sha256": null,
  "validator_output": "not run (no candidate raster)",
  "submission_name": null,
  "submission_note": null,
  "verdict": "negative",
  "verdict_reason": "BLOCKED: native lidar unreachable; no candidate meets the gate. No download offered. No submission slot used.",
  "experiments_used": 0,
  "submission_slots_used": 0
}
```

Note: `experiments_used` is 0 because this session ran diagnostics and reproducible checks, not a scored candidate experiment.

---

## 8. Next steps (in order)

1. **Decide the data route** (`IR-S-06`): either allow USGS 3DEP for this sandbox, or supply authorised 1 m DEM tiles with recorded SHA-256 under `data/`. Nothing else in the lane can move without this.
2. Once tiles are present: rebuild the native feature stack through the shared `gemsdoe66` modules (no private fork), run the leakage canary per feature, then the whole-segment holdout.
3. Re-run the registry duplicate gate on the full set of 60 registry .tif rasters, on both the pre-placement surface and the final dots.
4. Obtain an organizer receipt (or record its absence) for H33-2-B2 and the 0.3774 / 0.3195 leaderboard values.
5. Reviewer decisions on `IR-S-02` (catalogue vs labels semantics) before any holdout truth is defined.

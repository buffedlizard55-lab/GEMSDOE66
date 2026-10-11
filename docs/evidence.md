---
layout: default
title: Evidence ledger and repository review
---

# Evidence ledger and repository review

**Audit date:** 2026-10-11 UTC. The inventory statements below are local checkout observations. External method and competition statements are linked in [Sources](sources.md). Score evidence classes are deliberately separated from method descriptions.

## Line-by-line requirement audit

| Requirement or claim | Evidence class | What was checked | Result and limitation |
|---|---|---|---|
| The competition seeks faults indicative of geothermal resources. | OFFICIAL-SOURCE | DrivenData problem and About pages. | Verified. It is not a direct geothermal-vent detection task. Lidar-only methods address exposed topographic evidence and will miss buried faults. |
| Existing fault labels are incomplete and the challenge uses new expert-labelled faults. | OFFICIAL-SOURCE | DrivenData problem page. | Verified at the task-description level. The actual hidden test labels are not accessible here. |
| Competition data include 100 m projected features and a CSV of 1 m DEM links. | OFFICIAL-SOURCE | DrivenData problem description and rules PDF. | Verified from public text. The actual files were not downloaded; the data tab resolved to a login page. |
| The 1 m DEM route is publicly obtainable. | OFFICIAL-SOURCE, PARTIAL | USGS National Map 3DEP S1M catalog record, which is public. | A public USGS product exists. The precise competition-footprint tiles, link manifest, vertical/horizontal alignment, and bytes remain unverified. Do not treat this as an acquired input. |
| Slope-aware scarp templates are scientifically motivated. | PEER-REVIEWED / CONFERENCE ABSTRACT | Sare & Hilley template-matching paper and the official AGU abstract T31A-2838. | The literature describes scarp-profile templates and states that finite initial slopes and above-/below-scarp surface angles can improve detection over vertical templates in synthetic tests; the abstract reports DEM analysis at Surprise Valley and the Teton rangefront. It does not validate this branch's implementation or holdout. |
| Steger sub-pixel and Frangi multiscale line measures can be applied to a detrended DEM. | LITERATURE-BASED HYPOTHESIS | Original IEEE and Springer paper records. | The source methods concern curvilinear structures / vessel enhancement. Their use for fault scarps is an empirical transfer, with natural and cultural line mimics. No output was calculated here. |
| The official score is distance-weighted Tversky. | OFFICIAL-SOURCE SPECIFICATION, NOT A GEMSDOE66 SCORE | DrivenData metric definition. | Formula and parameters are published by the competition. This is a metric specification, not a result. The official metric uses a 300 m triangular distance kernel and weights false negatives more than false positives. |
| Required raster format is one float32 layer on EPSG:32611 at the official 100 m grid with values in `[0,1]` and null/NaN outside. | OFFICIAL-SOURCE SPECIFICATION, NOT A VALIDATION RESULT | DrivenData submission-format section. | Verified as the published contract. No candidate file exists to validate. The user's requested in-footprint finite/NaN-outside checks remain unrun. |
| The current checkout has the shared cached stack and evaluator/writer. | LOCAL INVENTORY | `git ls-files`, root directory listing, and `find` at session start. | **False for this checkout.** At session start the only tracked file was the 11-byte README. No cached stack, `evaluate_holdout.py`, `submission_writer.py`, `validate_submission.py`, mask, data directory, registry, or prior raster was present. |
| The stale prompt instruction to run `scripts/download_competition_data.sh` and `scripts/prepare_data.py` can be executed here. | LOCAL INVENTORY | File-tree inspection. | **False for this checkout.** Neither script exists. The data page requires sign-in. No credentials were requested or stored. |
| The H33-2-B2 file produced the prompt-attributed leaderboard result. | OWNER-REPORTED / UNVERIFIED FILE ATTRIBUTION | GEMSDOE32's artifact page and a separate sibling page's attribution. | Not established by an organizer submission receipt or a hash-to-row match in this checkout. GEMSDOE32 labels its H33 artifact unscored and calls its projected value a model, not a score; 59GEMSDOE labels the row-to-artifact attribution owner-reported. Do not state a causal explanation as fact. See [Decision log](decision-log.html). |
| Prior projects already tried related lidar methods. | OWNER-REPORTED METHOD CONTEXT | The linked 7GEMSDOE, GEMSDOE46, and GEMSDOE47 pages. | Yes, related scarp-channel, ridge-thinning, and consensus ideas are described on those pages. Their artifacts were not downloaded or included in a complete registry; uniqueness cannot be determined from prose alone. |
| A current leaderboard feed can be mirrored automatically. | PLATFORM TERMS CHECK | DrivenData Terms of Use. | Do not implement a scraper or copied score feed without prior written consent. The site links to the official live leaderboard but does not poll or mirror it. |

## Three-pass implementation review

### Pass 1 — implement

Expanded the standing brief in `README.md`; built the fail-closed static Pages site and executive submission guide; wrote four ranked, single-lane hypotheses; created the official/owner-source evidence register; and recorded the blocked run as a negative JSON card. No prior TIFF was copied and no synthetic placeholder was emitted.

### Pass 2 — review and correct

Reconciled the H33 artifact-page statement against sibling-site score attribution; separated official metric specifications, owner reports, and score receipts; found the exact competition-data login gate and the platform restriction on leaderboard monitoring; confirmed the expected download/preparation scripts and shared evaluation/writer tools are absent; and made the page explicitly say no file may be downloaded or submitted. A site-link audit also found that Jekyll layout links must be resolved from the published root, not the template directory; the audit now accounts for generated Markdown pages and checks that no TIF/TIFF/ZIP link or artifact can be exposed in the negative state.

### Pass 3 — re-check against the full request

Re-read the README and all requirements. The home page and executive summary put clearance first; the run card contains the hypothesis, mechanism, named non-fault mimics, null holdout/CI/evaluator/positive fields, unrun surface/final-dot registry checks, null raster hash, unrun validator checks, no submission name, a short no-upload note, and `negative` verdict. The top hypothesis remains unvalidated because the shared inputs/tools are absent; no weekly slot was touched. Final local checks are listed below; the TIFF validator itself cannot run without a TIFF and template.

## Result of this review

- **HOLDOUT-DTI:** `NOT RUN`. There is no evaluator version, withheld-positive count, or confidence interval because the evaluator and inputs are absent. This is not a zero score.
- **Leakage canary:** `NOT RUN`. No feature raster or held-out labels exist locally.
- **Registry uniqueness:** `NOT RUN BEFORE PLACEMENT`. No surface was made, so no dots were placed; the complete registry is absent.
- **Submission writer / validator:** `NOT RUN`. The shared scripts and sample template are absent.
- **TIF output:** none. No previous submission was copied, and no dummy or zero raster was created.
- **Download / submit clearance:** `NO`. No file exists; no weekly slot was used.
- **Experiments:** none. The correct decision was to stop before experiment because the mandated shared inputs/tools cannot be reused.
- `nvidia-smi` is not installed in this environment; GPU availability was **not verified**. No model-training claim is made.

The machine-readable status is [run-card.json](evidence/run-card.json). The site audit script verifies that this negative state cannot accidentally expose a TIFF link.

## Discrepancies and irregularities to retain

1. **H33 score provenance conflict:** the prompt presents an H33-associated value as a score; GEMSDOE32 says the artifact has no organizer score, while another owner page attributes a public leaderboard row to it. An official receipt and artifact hash are required to resolve this.
2. **Stale/contradictory leaderboard claims:** the prompt itself gives multiple different values and calls different values “current.” The official public board is mutable. No static number in this project is treated as a current leaderboard value; the site links to the live source instead.
3. **Sibling-site evidence classes vary:** some sibling pages publish local proxy DTI, projections, or unreceipted score attribution alongside download links. Those are not interchangeable with an organizer-confirmed score. Keep the evidence label next to every numeric claim.
4. **Format error is not diagnosed for the user's previous file:** the official contract requires `[0,1]` predictions and null/NaN outside. Without the rejected file and portal receipt, the error's actual cause cannot be determined. Do not assume that a “range” message proves whether a nodata sentinel, an in-footprint value, or a parser issue was responsible.
5. **Cultural-feature mask absent:** the requested road/canal/field-edge masking cannot be performed until the shared mask is made available. No substitute mask was invented.
6. **The line about existing scripts is stale for this branch:** the named download and preparation scripts are not in the checkout. Running similarly named commands would be fabricated execution.
7. **Sibling result-status mismatch:** the prompt lists score-like results for some lidar entries, while the corresponding 7GEMSDOE/GEMSDOE47/GEMSDOE46 owner pages describe relevant files as unscored, unsubmitted, or local-proxy-only. Submission receipts and exact file hashes are needed before any of those figures can be called organizer-confirmed.
8. **Pages configuration mismatch:** repository settings initially pointed GitHub Pages at the `main` branch root, and the public URL showed only the README. This branch adds a Pages Actions workflow, but the deployed site is not claimed live until the repository is configured for Actions and the deployment succeeds.

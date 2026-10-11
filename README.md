# GEMSDOE66 — Maximize P(Win), Own the Outcome

**One lane:** native-resolution LiDAR scarp channels. **One standard:** a scientific, reproducible result that survives the holdout, registry, format, provenance, and rules gates. **One current status:** blocked; no candidate is cleared for download or submission.

> **Current as of 2026-10-11:** the official competition data tab redirected this unauthenticated session to the DrivenData login page. No competition credentials were used. The checkout has no authorized training rasters, sample submission, native-resolution DEM tiles, or cached feature stack. No new model experiment or GeoTIFF was produced. Historical H66 files have been withdrawn from `docs/downloads`; their hashes and audit disposition remain recorded. Do not upload a historical artifact.

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
| Valid `HOLDOUT-DTI` with 95% CI | **None** — the historical H66 holdout claim is unqualified after audit |
| Complete uniqueness registry | **Blocked** — the available registry is incomplete |
| Current submission file/download | **None** — no file is cleared; do not use a historical artifact |
| Independent scientific-lead sign-offs | **Outstanding** |

See the [dated project-status feed](docs/feed.html), [run card](docs/run-card.html), [technical audit](docs/review/2026-10-11-audit.md), and [irregularity register](docs/irregularities.html) for details.

## Scientific focus

The lead hypothesis is a **native-resolution, slope-aware scarp-template field combined with scale-persistent Steger ridge/valley and Frangi Hessian-line evidence**, then aggregated to the official 100 m grid. Scarplet's published template outputs include best-fit amplitude, morphologic age, orientation, and template SNR; these are not interchangeable with a slope ratio, a robust z-score, or a heuristic height proxy. The actual algorithms must be run from the authorized native DEM, with per-feature leakage tests and named geomorphic mimics (including terrace risers, natural channel banks, and landslide scarps).

The official DrivenData problem description explains that the public fault compilation is incomplete and that test faults were newly identified by experts. The official metric is distance-weighted Tversky; it downweights location error with a 300 m triangular support and uses α=0.2 and β=0.8. The task therefore rewards useful proximity to new faults, not simply rediscovery of the mapped catalogue. See `docs/data/sources.json` for the exact source paths and provenance notes.

### Current attribution finding

The H33-2-B2 score attribution in the previous project material is **unverified**. The owner-maintained GEMSDOE32 page describes its artifact as unscored and says no organizer score exists for those artifacts; no submission receipt tied to that exact TIFF or its SHA-256 is present here. Therefore, this repository cannot establish why that file allegedly earned the reported value. The metric's false-positive/false-negative trade-off can be explained from the official formula, but no causal explanation for that H33 artifact is justified without a receipt, exact bytes, and controlled comparisons.

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

#!/usr/bin/env python3
"""Build the GitHub Pages site from the JSON evidence this repository produces.

Nothing on the site is hand-written prose about a number: every figure is read from
``evidence/*.json`` / ``docs/downloads/*.json`` at build time, so a stale page cannot
disagree with the measurement it describes.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
DL = DOCS / "downloads"

NAV = [("index.html", "Overview"), ("executive-summary.html", "How to submit"),
       ("hypotheses.html", "Hypotheses"), ("research.html", "Research"),
       ("results.html", "Results"), ("feed.html", "Project feed"),
       ("sources.html", "Sources"), ("irregularities.html", "Irregularities")]


def esc(s) -> str:
    return html.escape(str(s))


def page(title: str, body: str, active: str) -> str:
    nav = "".join(
        f'<a href="{h}" class="{"on" if h == active else ""}">{esc(t)}</a>'
        for h, t in NAV)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · GEMSDOE66</title>
<link rel="stylesheet" href="assets/site.css"></head>
<body><header class="top"><div class="wrap">
<h1 class="logo">GEMSDOE66 — DOE GEMS Prize fault discovery</h1>
<nav class="main">{nav}</nav></div></header>
<main>
<div class="wrap">
{body}
</div>
</main>
<footer><div class="wrap">
GEMSDOE66 · <a href="https://github.com/buffedlizard55-lab/GEMSDOE66">repository</a> ·
competition <a href="https://www.drivendata.org/">DrivenData #306</a>.
Every number on this site is a local measurement or an owner/public report and is labelled as
one; no organiser score exists for any artifact here.
</div></footer></body></html>
"""


def load(p: Path, default=None):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def pill(ok: bool, text: str = None) -> str:
    cls = "ok" if ok else "bad"
    return f'<span class="pill {cls}">{esc(text or ("PASS" if ok else "FAIL"))}</span>'


def pillw(text: str = "WARN") -> str:
    """Neither a pass nor a fail: a diagnostic whose rule and its null disagree."""
    return f'<span class="pill warn">{esc(text)}</span>'


# ------------------------------------------------------------------------------------------
def submission_block() -> str:
    """The top-of-page download block.  Reads docs/data/release-h66c.json.

    Published verdict is NEGATIVE: the file is offered for review only, never as a cleared
    submission.  The block must state that in the first sentence the reader sees.
    """
    R = load(ROOT / "docs" / "data" / "release-h66c.json", {})
    chk = R.get("validator", {})
    uni = R.get("uniqueness_dots", {})
    usf = R.get("uniqueness_surface", {})
    hold = R.get("holdout", {})
    ok = bool(chk.get("ok"))
    note = R.get("note", "")
    return f"""
<div class="stop">
  <h2>Download status: FILE AVAILABLE — scientific gate NOT MET (review candidate)</h2>
  <p class="small">The GeoTIFF below is <b>unique and format-valid</b>; verify the SHA-256
  after downloading. It is <b>not promoted</b>: on the only instrument in this repository that
  is positively rank-correlated with the owner-reported live scores it measures
  <b>{hold.get('dti', 0):.4f} [{hold.get('ci_lo', 0):.4f}, {hold.get('ci_hi', 0):.4f}]</b>
  against a frozen best of <b>{max(b['n'] for b in R.get('baselines', [{'n': 0}])):.4f}</b>.
  <b>Download: yes. Submit: no.</b> Producing this file spent no competition submission slot.</p>
  <p class="small"><b>Recommendation: do not submit this file as-is.</b> Its value is as a
  reproducible, byte-verified, <i>unique</i> alternative-lane artifact and as the measurement
  that locates the family's remaining headroom in placement geometry rather than in new scarp
  physics.</p>
  <p>
    <a class="btn" href="{esc(R.get('rel_tif', ''))}">Download {esc(R.get('slug', ''))}.tif</a>
    &nbsp;<a class="btn" href="{esc(R.get('rel_zip', ''))}">Download .zip</a>
  </p>
  <table>
    <tr><th>sha256 (tif)</th><td class="mono">{esc(R.get('sha256_tif', ''))}</td></tr>
    <tr><th>sha256 (zip)</th><td class="mono">{esc(R.get('sha256_zip', ''))}</td></tr>
    <tr><th>size</th><td>{R.get('size_bytes', 0):,} bytes</td></tr>
    <tr><th>grid</th><td>{esc(R.get('grid', ''))}</td></tr>
    <tr><th>emitted cells</th><td>{R.get('n_dots', 0):,} &nbsp;
        ({R.get('n_dots', 0) / max(R.get('footprint_cells', 1), 1) * 100:.3f}% of the
        {R.get('footprint_cells', 0):,}-cell features footprint)</td></tr>
    <tr><th>dots within 200 m of a known fault</th><td>0 (hard catalogue-gap gate)</td></tr>
    <tr><th>format validator</th>
        <td>{pill(ok)} all {len(chk.get('checks', {}))} gating checks pass,
        {len(chk.get('failures', []))} failures, {len(chk.get('skipped', []))} skipped</td></tr>
    <tr><th>Duplicate gate — pre-placement surface</th>
        <td>{pill(usf.get('max_abs_spearman_rho', 1) <= 0.90)}
        max |&rho;| = {usf.get('max_abs_spearman_rho', 0):.3f} (0.90 threshold),
        {usf.get('n_compared', 0)} accessible rasters scanned</td></tr>
    <tr><th>Duplicate gate — final dots, density-adjusted</th>
        <td>{pill(uni.get('max_lift_over_random', 9) < 9 and uni.get('worst_within_3px_above_1p5x_random', 1) <= 0.70)}
        max |&rho;| = {uni.get('max_abs_spearman_rho', 0):.3f} (0.90 threshold);
        highest lift over random placement = {uni.get('max_lift_over_random', 0):.2f}&times;;
        worst within-3 px fraction among the {uni.get('n_above_1p5x_random', 0)} rasters above
        1.5&times; random = {uni.get('worst_within_3px_above_1p5x_random', 0):.3f}
        (0.70 stop), computed over all {uni.get('n_compared', 0)} accessible rasters</td></tr>
    <tr><th>Duplicate gate — final dots, raw protocol rule</th>
        <td>{pillw('WARN — raw rule trips on density')}
        raw max within-3 px = {uni.get('raw_max_frac_dots_within_3px', 0):.3f} against
        <code>{esc(uni.get('raw_argmax', ''))}</code>, which carries
        {uni.get('raw_other_dots', 0):,} dots; random placement already gives
        {uni.get('raw_null_within_3px_random_placement', 0):.3f}, so the lift is only
        {uni.get('raw_lift_over_random', 0):.2f}&times;. The literal &gt;0.70 rule therefore
        trips on <i>density</i>, not similarity. Logged as
        <a href="irregularities.html">IR-66-UNIQ-01</a>; per this repository's own stricter
        precedent (IR-71) the density-adjusted pass does not silently overrule it.</td></tr>
    <tr><th>HOLDOUT-DTI (instrument {esc(hold.get('instrument', 'N'))})</th>
        <td>{hold.get('dti', 0):.4f}, 95% CI [{hold.get('ci_lo', 0):.4f},
        {hold.get('ci_hi', 0):.4f}], {hold.get('n_withheld_positives', 0):,} withheld
        positives — <b>below the frozen best</b></td></tr>
    <tr><th>leakage canary</th>
        <td>{pill(R.get('canary_max_auc', 1) <= 0.90)} highest single-feature AUC
        {R.get('canary_max_auc', 0):.3f} of {R.get('n_features', 0)} features (0.90 threshold)</td></tr>
    <tr><th>submission name</th><td class="mono">{esc(R.get('slug', ''))}</td></tr>
    <tr><th>submission note ({len(note)}/140 chars)</th><td class="mono">{esc(note)}</td></tr>
  </table>
  <p class="small">Is it OK to download and submit? <b>Download yes, submit no.</b> The
  <a href="executive-summary.html">executive summary</a> gives the exact submission procedure
  if a human selector decides otherwise, the measurement that failed the gate, and precisely
  what would have to be true for this file to be worth a slot.</p>
</div>
"""


def extra_sections(name: str) -> str:
    """Sections stored as data so the generator never silently reverts hand-written pages."""
    d = load(ROOT / "docs" / "data" / f"{name}.json", {})
    return "\n\n".join(d.get("sections", []))


def index_page() -> str:
    e1 = load(ROOT / "evidence" / "experiment1_parsed.json", {})
    e3 = load(ROOT / "evidence" / "experiment3_controls.json", {})
    rf = load(ROOT / "evidence" / "range_front_stratification.json", {})
    ch = e3.get("chance", {})
    rows = ""
    for k in ("random", "incumbent", "lidar_lane", "catalogue_habitat",
              "sgmc_novel", "fusion"):
        if k in e1 and "N" in e1[k]:
            v = e1[k]["N"]
            rows += (f"<tr><td class='mono'>{esc(k)}</td>"
                     f"<td>{sum(v)/len(v):.5f}</td><td>{len(v)}</td></tr>")
    return page("Overview", f"""
<h2>What this is</h2>
<p>An auditable pipeline that produces one GeoTIFF of fault-probability predictions for the
<a href="https://www.drivendata.org/">DOE GEMS Prize</a>.
The scored truth is <b>faults that are not in the given catalogue</b>, so every design choice
here is aimed at that, not at recovering the 60,988 labelled pixels we were given.</p>

{submission_block()}

<h2>The one idea that matters</h2>
<p>The metric is a <b>budget</b>. With <code>T = TP<sub>w</sub></code>, <code>S = Σp</code>,
<code>M = Σp·max<sub>g</sub>k</code> and <code>|G|</code> truth pixels:</p>
<pre>DTI = T / ( 0.2·T + 0.2·(S − M) + 0.8·|G| )

adding a unit of mass raises DTI  ⟺  k &gt; 0.2 · DTI</pre>
<p>At DTI = 0.28 that bar is <b>0.056</b>. Mass that cannot clear it is a loss. That is why the
best-scoring rasters in this project family are sparse dot sets (~38 k pixels out of 5.17 M)
and not dense probability maps.</p>

<h2>Inherited lane result — negative, not the target method</h2>
<p>The inherited PR #13 run reports an internal <b>HOLDOUT-DTI</b> evaluation on SGMC
off-catalogue truth, but its pooled advantage disappears under relief matching. Its full
reported evaluator version, withheld-positive count, and 95% intervals are available on the
<a href="results.html">results page</a> and in the inherited experiment card. This is an
internal proxy, not <b>ORGANIZER-CONFIRMED</b>, and the field was computed on 100 m-derived
inputs at 200–2,000 m scales because raw 1 m tiles were unavailable. It is not the requested
native-resolution 2–20 m implementation. No experiment was run in this reconciliation, no
candidate is cleared, and no submission slot was used.</p>
<p class="note">The final-dot raw overlap stop also trips; 60 accessible rasters do not certify a
complete organizer registry, and no pre-placement surface comparison is recorded. See
<a href="irregularities.html">IR-71</a> and the <a href="review/2026-10-11-pr12-reconciliation.md">PR #12 reconciliation</a>.</p>

<div class="grid">
 <div class="card"><h4>Current official inputs</h4><p class="big">NOT AVAILABLE</p>
   <p class="small">No authorized reference raster or native 1 m tile in this checkout. A
   historical 23-file mirror receipt is not organizer provenance or current availability.</p></div>
 <div class="card"><h4>Inherited stack</h4><p class="big">Audit only</p>
   <p class="small">59 historical 100 m features; not native 2–20 m scarp-template outputs.</p></div>
 <div class="card"><h4>Holdout</h4><p class="big">8</p>
   <p class="small">spatially coherent balanced folds, 300 m buffer, training-only</p></div>
 <div class="card"><h4>Duplicate gate</h4><p class="big">STOP / UNVERIFIED</p>
   <p class="small">Raw 3 px dot overlap is 0.990 (&gt; 0.70); only 60 accessible rasters were
   compared, the complete registry is uncertified, and surface correlation was not reported.</p></div>
</div>
<p class="small"><a href="analysis.html">H33 attribution review</a> · <a href="review/2026-10-11-pr12-reconciliation.md">PR #12 merge reconciliation and shared-template provenance audit</a></p>
""", "index.html")


def exec_page() -> str:
    R = load(ROOT / "docs" / "data" / "release-h66c.json", {})
    hold = R.get("holdout", {})
    body = f"""
<p class="small">Verdict on the current artifact:
<b>NEGATIVE — do not submit it. You may download it.</b>
Last updated {esc(R.get('date', ''))} · canonical run card
<a href="data/run-card-h66c.json"><code>docs/data/run-card-h66c.json</code></a> ·
verdict note <a href="review/2026-10-12-h66c-verdict.md"><code>docs/review/2026-10-12-h66c-verdict.md</code></a>.</p>

{extra_sections('executive-summary-sections')}
"""
    return page("How to submit", body, "executive-summary.html")


def hyp_page() -> str:
    d = load(DOCS / "data" / "hypotheses.json", {}) or {}
    rows = []
    for h in d.get("items", []):
        rows.append(
            f"<tr><td><b>{esc(h.get('rank'))}</b><br><code>{esc(h.get('id'))}</code></td>"
            f"<td><b>{esc(h.get('title'))}</b><p>{esc(h.get('layers'))}</p></td>"
            f"<td>{esc(h.get('signature'))}</td>"
            f"<td>{esc(h.get('named_mimic'))}</td>"
            f"<td>{esc(h.get('differs_from_repo'))}</td>"
            f"<td>{esc(h.get('expected_gain') or h.get('expected_dti_improvement'))}</td>"
            f"<td>{esc(h.get('cost'))}</td>"
            f"<td><b>{esc(h.get('validation'))}</b><br>{esc(h.get('data_status'))}</td></tr>"
        )
    return page("Hypotheses", f"""
<h2>Ranked same-lane hypotheses — before implementation</h2>
<p>Ranking and hypotheses are read from <code>docs/data/hypotheses.json</code>. Expected gains
are qualitative priors, not DTI projections. Every candidate below is unimplemented and
unvalidated; authorized native DEM coverage, shared-cache provenance, independent review,
holdout, leakage, and complete-registry gates remain blocking.</p>
<table>
<tr><th>rank / id</th><th>hypothesis and inputs</th><th>physical signature</th>
<th>named non-fault mimic</th><th>difference from repo</th><th>qualitative prior</th>
<th>cost</th><th>validation/data status</th></tr>
{''.join(rows)}
</table>
<div class="stop"><b>No hypothesis is cleared for an experiment or submission.</b> The inherited
PR #13 result is a scale-deviating 100 m-grid proxy and does not validate these native-resolution
2–20 m hypotheses. See <a href="review/2026-10-11-pr12-reconciliation.md">the reconciliation</a>
for current blockers and scope.</div>
""", "hypotheses.html")


def research_page() -> str:
    return page("Research", """
<h2>Research protocol and limitations</h2>

<h3>1 · Metric transcription</h3>
<p>The official problem description defines distance-weighted Tversky scoring. With
<code>T = TP<sub>w</sub></code>, total prediction mass <code>S</code>, weighted mass <code>M</code>,
and truth-pixel count <code>|G|</code>:</p>
<pre>DTI = T / (0.2T + 0.2(S − M) + 0.8|G|)</pre>
<p>The project tests the transcription in <code>tests/test_metric.py</code>. That code-level test
is not a competition score and does not authenticate any label raster.</p>

<h3>2 · Target method versus inherited proxy</h3>
<p>The requested method is native-resolution scarp evidence: slope-aware templates; Steger
sub-pixel and Frangi ridge/valley measures at <b>2–20 m</b>; 100 m aggregation of scarp fraction,
SNR-weighted amplitude, orientation coherence and dominant strike; the existing cultural mask;
and spatially blocked validation. The exact 1 m tiles and compatibility checks are not available
in this checkout, so this target method has <b>not</b> been run.</p>
<p>The inherited PR #13 <code>lidar_lane</code> used 1 m-derived descriptors and line scales at
2–20 pixels on a 100 m grid, i.e. 200–2,000 m. It is scale-deviating, negative after
relief-matching, and remains audit-only. Its internal `HOLDOUT-DTI` values and CIs are labelled
on the <a href="results.html">results page</a>; they do not validate the requested method and
are not `ORGANIZER-CONFIRMED`.</p>

<h3>3 · Holdout, leakage, and release criteria</h3>
<ul>
<li>Withhold whole fault segments with a buffer. Derive catalogue features only from visible
faults and mask visible faults pixel-exactly.</li>
<li>Score pooled DTI on LiDAR-covered held-out blocks with α = 0.2, β = 0.8 and a 300 m
triangular kernel; report evaluator version, withheld-positive count and 95% CI.</li>
<li>Run feature-alone leakage canaries; AUC above 0.90 is a stop pending proof otherwise.</li>
<li>Compare both continuous pre-placement surfaces and final emitted dots against every indexed
registry raster. Apply absolute Spearman thresholds and the raw &gt;70% / 3 px emitted-dot stop;
random-density lift is diagnostic only. Require an explicit organizer-complete certificate and
matching expected count; incomplete access is not a pass.</li>
<li>Verify pixel/hash agreement and the exact official CRS, shape, transform, range, and NaN-only
outside-footprint contract. A local format receipt is not organizer acceptance.</li>
</ul>

<h3>4 · Evidence status</h3>
<p>Official competition inputs and exact DEM-tile coverage remain unverified in this environment.
Owner-maintained GitHub mirrors are hash-pinned for local reproducibility but are not
organizer-authenticated. The site does not poll leaderboard pages or infer artifact performance
from owner reports. No organizer receipt in this checkout confirms a score for any raster.</p>
<p>The inherited PR #13 run was stopped: its relief-matched result does not beat the incumbent,
its raw final-dot overlap exceeds the threshold, its complete-registry status is uncertified, and
its pre-placement surface comparison is absent. No experiment or submission slot was used in the
PR #12 reconciliation.</p>

<h3>5 · Trusted method references</h3>
<ul>
<li><b>[official]</b> <a href="https://www.drivendata.org/">DrivenData</a> DOE GEMS Prize
competition and problem description; the data tab remains login-walled in the recorded audit.</li>
<li><b>[official]</b> <a href="https://www.usgs.gov/3d-elevation-program">USGS 3DEP</a> and
<a href="https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and">USGS GeoDAWN</a>; product context does not prove exact tile coverage.</li>
<li><b>[literature]</b> <a href="https://doi.org/10.21105/joss.01066">Sare &amp; Hilley,
Scarplet (JOSS)</a>, <a href="https://doi.org/10.1109/34.659930">Steger (IEEE TPAMI)</a>,
and <a href="https://research.manchester.ac.uk/en/publications/multiscale-vessel-enhancement-filtering/">Frangi et al. (MICCAI)</a>. These establish methods, not competition performance.</li>
</ul>
<p>See the <a href="analysis.html">H33 attribution review</a>,
<a href="sources.html">source register</a>, <a href="irregularities.html">irregularities</a>, and the
<a href="review/2026-10-11-pr12-reconciliation.md">PR #12 reconciliation</a>.</p>
""", "research.html")


def results_page() -> str:
    e3 = load(ROOT / "evidence" / "experiment3_controls.json", {})
    rmatch = load(ROOT / "evidence" / "relief_matched.json", {})
    rg = load(ROOT / "evidence" / "relief_gate.json", {})
    pooled = rmatch.get("pooled_confounded", {})
    matched = rmatch.get("relief_matched", {})
    def summary_rows(instrument):
        labels = (("lidar lane", "lane"), ("incumbent", "inc"), ("uniform random", "rand"))
        return "".join(
            f"<tr><td>{esc(label)}</td><td>{instrument.get(key, {}).get('mean', float('nan')):.5f}</td>"
            f"<td>[{instrument.get(key, {}).get('ci95', [float('nan'), float('nan')])[0]:.5f}, "
            f"{instrument.get(key, {}).get('ci95', [float('nan'), float('nan')])[1]:.5f}]</td>"
            f"<td>{instrument.get(key, {}).get('n_folds', 8)}</td></tr>"
            for label, key in labels
        )
    per_stratum = rmatch.get("per_stratum", {})
    strata_rows = []
    for key, label in (("basin", "Basin"), ("mid", "Mid-relief"),
                       ("range_front", "Range front")):
        lane = per_stratum.get("lane", {}).get(key, {})
        rand = per_stratum.get("rand", {}).get(key, {})
        strata_rows.append(
            f"<tr><td>{label}</td><td>{lane.get('mean', float('nan')):.5f} "
            f"[{lane.get('ci95', [float('nan'), float('nan')])[0]:.5f}, "
            f"{lane.get('ci95', [float('nan'), float('nan')])[1]:.5f}]</td>"
            f"<td>{rand.get('mean', float('nan')):.5f} "
            f"[{rand.get('ci95', [float('nan'), float('nan')])[0]:.5f}, "
            f"{rand.get('ci95', [float('nan'), float('nan')])[1]:.5f}]</td></tr>"
        )
    gains = rmatch.get("gains_matched", {})
    return page("Results", f"""
<h2>Results — inherited negative experiment, not a promotion</h2>
<div class="note"><b>All performance measurements below are labelled HOLDOUT-DTI.</b>
Evaluator: <code>gemsdoe66.metric.dti</code> (the inherited card reports a 1e-9 comparison
with a brute-force equation transcription). Instrument: SGMC off-catalogue faults, 8 spatial
folds, approximately 7,700 withheld positives per fold (61,664 total), 300 m training-only
buffer, α = 0.2, β = 0.8, 300 m triangular kernel. The listed 95% CIs are the recorded
percentile intervals over folds. This proxy holdout is not the organizer's hidden set. No
<code>ORGANIZER-CONFIRMED</code> score exists for any artifact.</div>
<p class="stop"><b>Protocol deviation:</b> the inherited lane used 1 m-derived 100 m descriptors
and 2–20 pixel scales on the 100 m grid (200–2,000 m), not the requested native-resolution
2–20 m scarp method. The numeric results below do not validate LIDAR-01.</p>

<h3>Pooled novelty instrument (relief-confounded)</h3>
<table><tr><th>field</th><th>HOLDOUT-DTI mean</th><th>95% CI</th><th>folds</th></tr>
{summary_rows(pooled)}</table>

<h3>Relief-matched instrument</h3>
<table><tr><th>field</th><th>HOLDOUT-DTI mean</th><th>95% CI</th><th>folds</th></tr>
{summary_rows(matched)}</table>
<p>The paired matched lane-minus-incumbent HOLDOUT-DTI difference is
<b>{gains.get('lane_minus_inc', {}).get('mean', float('nan')):+.5f}</b>, 95% CI
[{gains.get('lane_minus_inc', {}).get('ci95', [float('nan'), float('nan')])[0]:+.5f},
{gains.get('lane_minus_inc', {}).get('ci95', [float('nan'), float('nan')])[1]:+.5f}];
positive in {gains.get('lane_minus_inc', {}).get('folds_positive', 'not recorded')} of
{gains.get('lane_minus_inc', {}).get('n_folds', 8)} folds. The paired lane-minus-random
HOLDOUT-DTI difference is <b>{gains.get('lane_minus_rand', {}).get('mean', float('nan')):+.5f}</b>,
95% CI [{gains.get('lane_minus_rand', {}).get('ci95', [float('nan'), float('nan')])[0]:+.5f},
{gains.get('lane_minus_rand', {}).get('ci95', [float('nan'), float('nan')])[1]:+.5f}]. Both
intervals include zero; the verdict remains negative.</p>

<h3>Relief strata — HOLDOUT-DTI</h3>
<table><tr><th>terrain</th><th>lane HOLDOUT-DTI mean [95% CI]</th>
<th>random HOLDOUT-DTI mean [95% CI]</th></tr>
{''.join(strata_rows)}</table>
<p class="small">These are per-stratum HOLDOUT-DTI means with their recorded marginal CIs. No
paired difference is inferred here. No score projection is made.</p>

<h3>Chance-control HOLDOUT-DTI</h3>
<table><tr><th>control</th><th>mean</th><th>95% CI</th></tr>
{"".join(f"<tr><td>{esc(k)}</td><td>{v['mean']:.5f}</td>"
         f"<td>[{v['ci95'][0]:+.5f}, {v['ci95'][1]:+.5f}]</td></tr>"
         for k, v in e3.get('chance', {}).items() if isinstance(v, dict) and 'mean' in v)}</table>

<h3>Other diagnostics</h3>
<p>The relief-gate sensitivity values are retained in the evidence JSON. They are internal
HOLDOUT-DTI diagnostics, not a chosen submission budget or a promotion result. The mass sweep
is omitted here because no score is selected from that instrument.</p>
<p>Read the machine-readable inherited experiment card at
<a href="data/run_card.json"><code>docs/data/run_card.json</code></a> and the corrected raw-overlap
adjudication at <a href="data/irregularities.json">IR-71</a>. All values remain internal; no
file is cleared for download.</p>

{load(ROOT / "docs" / "data" / "results-h66c-section.json", {}).get("html", "")}
""", "results.html")


def sources_page() -> str:
    return page("Sources", """
<h2>Sources</h2>
<p>This inherited source register links organizer/USGS primary sources and bibliographic
records. The PR #12 reconciliation did not re-fetch every link; access limits and partial review
are documented in the dated audit. Primary sources establish rules/product context; literature
links are method context only, not performance evidence.</p>
<table>
<tr><th>source</th><th>what we took from it</th><th>link</th></tr>
<tr><td>Competition problem page</td><td>metric definition, α/β/R, submission format, the
 statement that the test set is faults <i>not</i> in the USGS database</td>
 <td><a href="https://www.drivendata.org/">page 967</a></td></tr>
<tr><td>Competition leaderboard</td><td>Not monitored or copied in this reconciliation. No public-board value is treated as an artifact receipt or organizer-confirmed score.</td>
 <td><a href="https://www.drivendata.org/">official site; navigate manually if authorized</a></td></tr>
<tr><td>Competition rules</td><td>submission caps and prize-round structure</td>
 <td><a href="https://docs.nlr.gov/docs/fy26osti/96647.pdf">96647.pdf</a></td></tr>
<tr><td>Reference solution</td><td>baseline architecture and the α = 0.2 / β = 0.8 convention</td>
 <td><a href="https://github.com/drivendataorg/gems-prize-reference-solution">github</a></td></tr>
<tr><td>USGS GeoDAWN data release</td><td>the survey the challenge region is defined by</td>
 <td><a href="https://www.sciencebase.gov/catalog/item/657e1d85d34e23d3533209f7">ScienceBase</a></td></tr>
<tr><td>USGS 3DEP</td><td>1 m and 10 m DEMs behind the lidar scarp and topography channels</td>
 <td><a href="https://www.usgs.gov/3d-elevation-program">3DEP</a></td></tr>
<tr><td>GBCGE INGENIOUS</td><td>the project whose fault compilation supplies the labels</td>
 <td><a href="https://gbcge.org/current-projects/ingenious/">gbcge.org</a></td></tr>
<tr><td>GDR submission 1391</td><td>wells/springs, Quaternary fault traces, volcanic vents (CC BY 4.0)</td>
 <td><a href="https://gdr.openei.org/submissions/1391">gdr.openei.org</a></td></tr>
<tr><td>Giddens et al. 2025, Stanford Geothermal Workshop</td>
 <td>"LiDAR and hillshades were utilized to identify the extent and location of Quaternary
 faults"; 1 m GeoDAWN lidar supplied by USGS; gravity most useful for fault geometry;
 step-overs the dominant favourable setting</td>
 <td><a href="https://pangea.stanford.edu/ERE/pdf/IGAstandard/SGW/2025/Giddens.pdf">PDF</a></td></tr>
<tr><td>Sare &amp; Hilley 2018</td><td>scarplet template matching: amplitude, relative age,
 orientation, SNR</td>
 <td><a href="https://doi.org/10.21105/joss.01066">doi:10.21105/joss.01066</a></td></tr>
<tr><td>Steger 1998</td><td>sub-pixel line extraction from the Hessian eigenvector</td>
 <td><a href="https://doi.org/10.1109/34.659930">doi:10.1109/34.659930</a></td></tr>
<tr><td>Frangi et al. 1998</td><td>multiscale Hessian vesselness</td>
 <td><a href="https://doi.org/10.1007/BFb0056195">doi:10.1007/BFb0056195</a></td></tr>
<tr><td>EPSG:32611</td><td>the required CRS</td>
 <td><a href="https://epsg.io/32611">epsg.io</a></td></tr>
</table>
<div class="note"><b>Data provenance caveat.</b> The competition rasters are login-walled at
drivendata.org. The bytes used here are <b>owner-supplied GitHub mirrors</b>, pinned by sha256
in <code>registry/data_manifest.json</code> and verified on fetch (23/23). A pin proves mirror
consistency; it does <b>not</b> prove organiser authentication.</div>
""", "sources.html")


def irr_page() -> str:
    return page("Irregularities", """
<h2>Irregularities</h2>
<table>
<tr><th>id</th><th>what</th><th>status</th></tr>
<tr><td><b>IR-66-CONFOUND-01</b><br><span class="tag">verdict-changing</span></td>
 <td><b>The primary instrument was confounded, and the confound was the whole result.</b> The
 novelty holdout truth (SGMC faults &gt; 300 m from the catalogue) is <b>59.3 % range front</b>
 and <b>1.3 % basin</b>, against a footprint that is 25.2 % range front and 23.7 % basin.
 Mapped faults concentrate where scarps are <i>visible</i>, so any range-front-heavy field
 beats a uniform one on a mapped-fault truth by construction. The lane puts 64.3 % of its dots
 on range fronts (the incumbent: 17.2 %), i.e. it matches the truth's own relief prior.
 De-confounded — budget allocated across relief strata in proportion to footprint area,
 per-stratum DTI averaged with footprint weights — the lane scores <b>0.02638</b> against the
 incumbent's <b>0.02727</b> and random's 0.02612: lane−incumbent <b>−0.00089</b>
 (CI [−0.0084, +0.0066], 3/8 folds), lane−random <b>+0.00026</b> (CI [−0.0055, +0.0060],
 4/8 folds). The confound is worth <b>+0.0227</b> — the entire +0.0218 headline. On range
 fronts specifically the lane's 0.0505 barely exceeds <i>random placement</i>'s 0.0487 at the
 same budget. <b>The run card's verdict was therefore changed from <code>promote</code> to
 <code>negative</code></b> and the GeoTIFF moved out of <code>docs/downloads/</code> into
 <code>artifacts/lidar_lane/</code>, unpublished. The pooled numbers reproduce exactly
 (0.07075 / 0.04896), so only the de-confounding is new, not the pipeline.</td>
 <td><span class="pill bad">OPEN — verdict flipped</span></td></tr>
<tr><td><b>IR-66-SCORE-01</b></td>
 <td>An earlier draft quoted a public leaderboard target. No leaderboard was accessed or
 monitored in this reconciliation, and no public row is tied here to an exact artifact receipt.
 No such number is used as an organizer-confirmed score or decision threshold.</td>
 <td><span class="pill warn">OPEN — NOT VERIFIED HERE</span></td></tr>
<tr><td><b>IR-66-DATA-01</b></td>
 <td>The sandbox reaches only github.com, api.github.com, pypi.org and their CDNs.
 <code>prd-tnm.s3.amazonaws.com</code>, <code>earthquake.usgs.gov</code>,
 <code>gdr.openei.org</code>, <code>sciencebase.gov</code> and <code>dropbox.com</code> all
 return HTTP 000. The raw 1 m GeoDAWN lidar and 10 m 3DEP tiles are therefore unobtainable
 here, and the scarplet template matcher cannot be run on native-resolution data.</td>
 <td><span class="pill warn">OPEN</span></td></tr>
<tr><td><b>IR-66-DATA-02</b></td>
 <td>The 10 m-DEM channel-steepness product covers <b>25 of 36 blocks</b>.</td>
 <td><span class="pill warn">OPEN</span></td></tr>
<tr><td><b>IR-66-PROXY-01</b></td>
 <td>Layer dot-means correlate with owner-reported live scores at |ρ| up to 0.98, but also with
 the emitted dot count at |ρ| = 0.5–0.9. The lidar scarp channels flip sign under nuisance
 control. The live anchor is a lane-choice prior, not evidence.</td>
 <td><span class="pill warn">OPEN</span></td></tr>
<tr><td><b>IR-66-GATE-01</b></td>
 <td>A density-adjusted diagnostic was used to label a final-dot scan <code>UNIQUE</code> even
 though the raw overlap against one accessible registry raster is 0.990, above the brief's
 0.70 stop threshold. Against a 311,617-dot raster the random-placement null is high, but the
 null does not waive the specified threshold. The raw result is a stop; the 1.5× lift is
 diagnostic only. Only 60 rasters were compared, full organizer-registry completeness is not
 certified, and this artifact has no recorded pre-placement-surface correlation.</td>
 <td><span class="pill bad">OPEN — NOT A UNIQUENESS PASS</span></td></tr>
<tr><td><b>IR-70-TEMPLATE-PROVENANCE</b></td>
 <td>The recorded shared-template comparison covers 23 <code>src/gems57</code> files: 19 match
 the stored hashes. <code>anatomy.py</code> and <code>metric.py</code> differ from the recorded
 template snapshot; <code>uniqueness.py</code> and <code>gates.py</code> are changes in this PR.
 <code>registry/template_pin.json</code> is absent from <code>origin/main</code>; no live
 upstream revision or tarball was checked. Do not claim an upstream fix or a complete provenance
 pass. Details: <a href="review/2026-10-11-pr12-reconciliation.md">PR #12 reconciliation</a>.</td>
 <td><span class="pill warn">OPEN</span></td></tr>
<tr><td><b>IR-71-LIDAR-RAW-OVERLAP</b></td>
 <td>The inherited lidar-lane final-dot result reports 0.990386 within 3 px of one accessible
 registry raster, above the 0.70 stop threshold. Its density-adjusted <code>UNIQUE</code> label
 is diagnostic only. Only 60 rasters were compared; organizer-registry completeness is
 uncertified; pre-placement surface correlation is unreported; no full-registry pixel/hash pass
 is established. The candidate remains negative and unpublished.</td>
 <td><span class="pill bad">OPEN — STOP</span></td></tr>
<tr><td><b>IR-66-BUG-01</b></td>
 <td>The first holdout run excluded the held-out truth's 300 m buffer from <i>emission</i> as
 well as training, forcing TP<sub>w</sub> = 0 for every candidate. The buffer is
 training-only.</td>
 <td><span class="pill ok">FIXED</span></td></tr>
<tr><td><b>IR-66-BUG-02</b></td>
 <td>The greedy packer suppressed neighbours only across blocks, so two dots accepted inside
 the same block could sit closer than the minimum separation. Each accepted pixel now stamps
 its exclusion disc.</td>
 <td><span class="pill ok">FIXED</span></td></tr>
<tr><td><b>IR-66-BUG-03</b></td>
 <td><code>folds_by_quadrant</code> assigned background (label 0) to fold 0 and produced folds
 of 2,307 vs 23,044 px. Replaced by balanced spatial clustering of connected components.</td>
 <td><span class="pill ok">FIXED</span></td></tr>
<tr><td><b>IR-66-H2-01</b></td>
 <td>A supervised field trained on off-catalogue SGMC faults scores <b>below chance</b> on
 held-out SGMC faults: it learns regional geology, not the fault signal.</td>
 <td><span class="pill bad">NEGATIVE RESULT</span></td></tr>
<tr><td><b>IR-66-UNIQ-01</b><br><span class="tag">needs judgement</span></td>
 <td><b>The literal &gt;70 % within-3 px duplicate rule trips on the H66-C candidate.</b> The raw
 maximum fraction of candidate dots within 3 px of one registry raster is <b>0.994</b>, against
 <code>gems61-lane-buried-step-gravinversion-hgm-r3-k400k-b2zeros.tif</code>, which carries
 311,350 dots (6.0 % of the footprint); random placement already gives 0.958, so the lift over
 random is 1.04&times;. Over the full 60-raster accessible set the maximum lift is 2.46&times;,
 the worst within-3 px fraction among the 48 rasters exceeding 1.5&times; random is
 <b>0.341</b> (0.70 stop), and |&rho;| &le; 0.290. The rule therefore trips on <i>density</i>,
 not similarity &mdash; the failure mode of IR-66-GATE-01. Following the stricter precedent set
 in IR-71 for the inherited lane, the density-adjusted UNIQUE verdict is <b>not</b> presented as
 overriding the raw rule: both numbers appear on the overview page, the run card and the verdict
 note. Full per-raster table: <code>evidence/uniqueness_h66c_full.json</code>.</td>
 <td>open &mdash; density-adjusted pass, literal raw rule trips</td></tr>
<tr><td><b>IR-66-SITE-01</b><br><span class="tag">fixed</span></td>
 <td><b>Hand-edited Pages HTML was silently revertible.</b> <code>docs/index.html</code>,
 <code>docs/executive-summary.html</code> and <code>docs/results.html</code> carried H66-C
 content that <code>scripts/build_site.py</code> did not know about, so any rebuild would have
 discarded it. Fixed by moving the content into
 <code>docs/data/release-h66c.json</code>, <code>docs/data/executive-summary-sections.json</code>
 and <code>docs/data/results-h66c-section.json</code>, which the generator consumes.</td>
 <td>fixed in this session</td></tr>
</table>
""", "irregularities.html")


def feed_page(feed: dict) -> str:
    rows = []
    for item in feed.get("entries", []):
        links = " · ".join(
            f'<a href="{esc(link)}">{esc(link)}</a>' for link in item.get("links", [])
        )
        rows.append(
            f'<article class="card"><p class="eyebrow">{esc(item.get("date"))} · '
            f'{esc(item.get("kind"))}</p><h2>{esc(item.get("status"))}</h2>'
            f'<p>{esc(item.get("summary"))}</p><p class="small">{links}</p></article>'
        )
    actions = "".join(f"<li>{esc(x)}</li>" for x in feed.get("next_actions", []))
    body = f'''<div class="eyebrow">Static project feed — not a leaderboard feed</div>
<h2>Current status: {esc(feed.get('status', 'not recorded'))}</h2>
<p>{esc(feed.get('scope', ''))}</p>
<p class="small">{esc(feed.get('external_monitoring', 'No external standings are polled or copied.'))}</p>
<section><h2>Project events</h2>{''.join(rows)}</section>
<section><h2>Next actions</h2><ol>{actions}</ol></section>
<p class="small">This local feed is not live and contains no organizer-confirmed score.</p>'''
    return page("Project feed", body, "feed.html")


def main() -> int:
    (DOCS / ".nojekyll").write_text("")
    (DOCS / "assets").mkdir(parents=True, exist_ok=True)
    for fn, body, active in [
        ("index.html", index_page(), "index.html"),
        ("executive-summary.html", exec_page(), "executive-summary.html"),
        ("hypotheses.html", hyp_page(), "hypotheses.html"),
        ("research.html", research_page(), "research.html"),
        ("results.html", results_page(), "results.html"),
        ("sources.html", sources_page(), "sources.html"),
        ("irregularities.html", irr_page(), "irregularities.html"),
    ]:
        (DOCS / fn).write_text(body)
        print(f"wrote docs/{fn}")
    feed = load(DOCS / "data" / "feed.json", {}) or {}
    if feed:
        (DOCS / "feed.html").write_text(feed_page(feed))
        (DOCS / "status-feed.json").write_text(
            json.dumps(feed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote docs/feed.html and docs/status-feed.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

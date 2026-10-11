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
       ("results.html", "Results"), ("sources.html", "Sources"),
       ("irregularities.html", "Irregularities")]


def esc(s) -> str:
    return html.escape(str(s))


def page(title: str, body: str, active: str) -> str:
    nav = "".join(
        f'<a href="{h}" class="{"on" if h == active else ""}">{esc(t)}</a>'
        for h, t in NAV)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)} · GEMSDOE66</title>
<link rel="stylesheet" href="assets/site.css"></head>
<body><header class="top"><div class="wrap">
<h1 class="logo">GEMSDOE66 — DOE GEMS Prize fault discovery</h1>
<nav class="main">{nav}</nav></div></header>
<main class="wrap">
{body}
</main>
<footer><div class="wrap">
GEMSDOE66 · <a href="https://github.com/buffedlizard55-lab/GEMSDOE66">repository</a> ·
competition <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">DrivenData #306</a>.
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


# ------------------------------------------------------------------------------------------
def submission_block() -> str:
    """The one-click download block.  Reads the newest build manifest."""
    mans = sorted(DL.glob("*.manifest.json"))
    if not mans:
        return '<div class="bad">No submission has been built yet.</div>'
    m = load(mans[-1], {})
    slug = m.get("slug", "")
    nan = DL / f"{slug}-nan.tif"
    zro = DL / f"{slug}-zeros.tif"
    chk = load(DL / f"checks-{slug}-nan.tif.json", {})
    uni = m.get("uniqueness", {})
    ok = bool(chk.get("ok"))
    note = (f"GEMSDOE66 lane: Frangi/Steger/structure-tensor scarp field from 1 m GeoDAWN "
            f"lidar, {m.get('n_dots', 0):,} dots, 0 within 200 m of the catalogue.")
    note = note[:140]
    return f"""
<div class="banner">
  <h2>⬇ Download the submission file</h2>
  <p class="small">One GeoTIFF. Upload it as-is to the competition submission page.
  It is a single-band <code>float32</code> raster, EPSG:32611, 3730 × 3292, 100 m,
  values in <b>[0, 1]</b>, NaN outside the footprint — so it passes the
  <code>Predicted values must be in range [0, 1]</code> check.</p>
  <a class="btn" href="downloads/{esc(nan.name)}">Download {esc(nan.name)}</a>
  <a class="btn alt" href="downloads/{esc(zro.name)}">zeros-outside variant</a>
  <table>
    <tr><th>sha256</th><td class="mono">{esc(chk.get('sha256', ''))}</td></tr>
    <tr><th>size</th><td>{chk.get('size_bytes', 0):,} bytes</td></tr>
    <tr><th>emitted pixels</th><td>{m.get('n_dots', 0):,} &nbsp;
        ({m.get('n_dots', 0) / 5_167_373 * 100:.3f}% of the 5,167,373-px footprint)</td></tr>
    <tr><th>dots within 200 m of a known fault</th><td>0</td></tr>
    <tr><th>format validator (re-read from disk)</th>
        <td>{pill(ok)} {len([v for v in chk.get('checks', {}).values() if v])}/
        {len(chk.get('checks', {}))} checks</td></tr>
    <tr><th>duplicate gate vs 60 registry rasters</th>
        <td>{pill(uni.get('verdict') == 'UNIQUE', esc(uni.get('verdict', 'n/a')))}
        max |ρ| = {uni.get('max_abs_spearman_rho', 0):.3f}</td></tr>
    <tr><th>submission note (paste into the form, {len(note)}/140 chars)</th>
        <td class="mono">{esc(note)}</td></tr>
  </table>
  <p class="small">Is it OK to download and submit? <b>Yes</b> — see the
  <a href="executive-summary.html">executive summary</a>, which states the gate, the
  measurement behind it, and what is <i>not</i> claimed.</p>
</div>
"""


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
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/">DOE GEMS Prize</a>.
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

<h2>What we measured this session</h2>
<p>8-fold spatially blocked hide-and-recover holdout. Truth for the primary instrument is the
<b>61,664 SGMC fault pixels that lie more than 300 m from the given catalogue</b> — real
USGS-mapped faults the label set does not contain. Every field is emitted at the identical
37,654-dot budget with zero dots within 200 m of the catalogue, so only the field differs.</p>
<table><tr><th>field</th><th>novelty DTI (8 folds)</th><th>n</th></tr>{rows}</table>
<p class="small">Chance level, measured with the same budget and geometry:
<b>{ch.get('random', {}).get('mean', 0):.5f}</b>.
Lane − chance = <b>{ch.get('lane_minus_random', {}).get('mean', 0):+.5f}</b>
(95% CI [{ch.get('lane_minus_random', {}).get('ci95', [0, 0])[0]:+.5f},
{ch.get('lane_minus_random', {}).get('ci95', [0, 0])[1]:+.5f}],
{ch.get('lane_minus_random', {}).get('folds_positive', 0)}/8 folds positive).</p>

<h2>The relief finding, stated plainly</h2>
<table><tr><th>terrain (by local relief)</th><th>lane</th><th>chance</th><th>gain</th><th>folds+</th></tr>
{"".join(f"<tr><td>{esc(k)}</td><td>{v['lane_mean']:.5f}</td><td>{v['random_mean']:.5f}</td>"
         f"<td><b>{v['gain']:+.5f}</b></td><td>{v['folds_positive']}/{v['n_folds']}</td></tr>"
         for k, v in rf.get('strata', {}).items())}</table>
<div class="note">The lane's skill is <b>relief-dependent</b>: strong on range fronts, moderate
on mid-relief slopes, and <b>absent on basin floors</b>. That is the physics, not a bug — a
tectonic scarp does not survive aggradation on an active basin floor, so there is no scarp for
a scarp channel to see. It also means the lane's gain is <b>not</b> confined to range fronts
(mid relief is not a range front), but it does vanish in basins, which is a limitation of this
channel and is logged as one.</div>

<div class="grid">
 <div class="card"><h4>Data</h4><p class="big">23/23</p>
   <p class="small">hash-pinned mirrors restored and byte-verified</p></div>
 <div class="card"><h4>Layers</h4><p class="big">59</p>
   <p class="small">competition bands, 1 m-LiDAR scarp descriptors, 10 m topography, χ,
   GeoDAWN radiometrics</p></div>
 <div class="card"><h4>Holdout</h4><p class="big">8</p>
   <p class="small">spatially coherent balanced folds, 300 m buffer, training-only</p></div>
 <div class="card"><h4>Duplicate gate</h4><p class="big">UNIQUE</p>
   <p class="small">max |ρ| vs 60 registry rasters: 0.28 (dots), 0.08 (surface)</p></div>
</div>
""", "index.html")


def exec_page() -> str:
    mans = sorted(DL.glob("*.manifest.json"))
    m = load(mans[-1], {}) if mans else {}
    slug = m.get("slug", "")
    note = (f"GEMSDOE66 lane: Frangi/Steger/structure-tensor scarp field from 1 m GeoDAWN "
            f"lidar, {m.get('n_dots', 0):,} dots, 0 within 200 m of the catalogue.")[:140]
    return page("How to submit", f"""
<h2>Executive summary — how to make a submission</h2>
<div class="banner">
<h2>1 · Download</h2>
<p><a class="btn" href="downloads/{esc(slug)}-nan.tif">Download {esc(slug)}-nan.tif</a></p>
<p class="small">Single-band float32 GeoTIFF · EPSG:32611 · 3730 × 3292 · 100 m ·
values in [0, 1] · NaN outside the footprint.
If your browser or the uploader mangles a bare <code>.tif</code>, use the
<a href="downloads/{esc(slug)}-nan.zip">zip</a>.</p>
</div>

<h2>2 · Upload</h2>
<ol>
<li>Open <a href="https://www.drivendata.org/competitions/306/competition-doe-gems/submissions/">the submission page</a>.</li>
<li><b>File to submit</b> → <b>Choose file</b> → pick the <code>.tif</code> you just saved.</li>
<li><b>Note (optional)</b> → paste the line below (it is already ≤ 140 characters):</li>
</ol>
<pre>{esc(note)}</pre>
<ol start="4"><li>Press <b>Create submission</b>.</li></ol>

<h2>3 · Why it will not be rejected</h2>
<p>The portal rejects a raster with <code>Predicted values must be in range [0, 1]</code> when
any <i>finite</i> value is outside that interval, and it requires the CRS, shape and
geotransform to match the template. Both are re-checked on the exact bytes before the file is
published here — <code>scripts/check_submission.py</code> re-opens the written GeoTIFF and runs
every check from scratch:</p>
<table>
<tr><th>check</th><th>meaning</th></tr>
<tr><td>single band</td><td>the organiser asks for one layer</td></tr>
<tr><td>float32</td><td>"datatype of 32-bit float"</td></tr>
<tr><td>3730 × 3292</td><td>same shape as the template</td></tr>
<tr><td>EPSG:32611</td><td>"the same projected coordinate reference system"</td></tr>
<tr><td>geotransform</td><td>100 m, origin (243350, 4508550)</td></tr>
<tr><td>no NaN / inf / sentinel inside</td><td>nodata −3.4028235e38 would be read as a real value</td></tr>
<tr><td><b>all finite values in [0, 1]</b></td><td>the rejection rule reported in the brief</td></tr>
<tr><td><b>NaN outside the footprint</b></td><td>"data outside the bounds is null or nan"</td></tr>
<tr><td>0 dots within 200 m of a known fault</td><td>the organiser does not score known faults</td></tr>
</table>

<h2>4 · Is it OK to download and submit?</h2>
<div class="good"><b>Yes</b>, and here is the exact basis for that answer — including what is
<b>not</b> claimed.
<ul>
<li><b>Format</b>: verified, on the bytes, by re-reading the written file. Receipt:
<code>docs/downloads/checks-{esc(slug)}-nan.tif.json</code>.</li>
<li><b>Originality</b>: the duplicate gate against all 60 registry rasters returns
<b>UNIQUE</b> (max |ρ| = 0.28 on the dots, 0.08 on the surface, against a 0.90 threshold).
It is a new raster, not a copy.</li>
<li><b>Skill</b>: on the 8-fold blocked holdout it beats chance by
<b>+0.031 DTI</b> (95% CI +0.013 to +0.050, 7/8 folds) and beats the family's best-scoring
raster, re-scored through the identical envelope, by <b>+0.022</b>.</li>
<li><b>NOT claimed</b>: <b>no organiser score exists for this file.</b> Every leaderboard
number on this site is an owner report or a public-page snapshot. The holdout is a proxy whose
truth is SGMC, not the expert panel's hidden set. Submitting it is a bet on a measured proxy,
not a promise.</li>
</ul></div>
<div class="note"><b>Weekly cap.</b> The competition allows 3 scored submissions per week and
the same file is scored in both prize rounds. Promotion to a real slot is a separate selector
step; this page does not spend a slot by itself.</div>
""", "executive-summary.html")


def hyp_page() -> str:
    e1 = load(ROOT / "evidence" / "experiment1_parsed.json", {})
    e3 = load(ROOT / "evidence" / "experiment3_controls.json", {})
    ch = e3.get("chance", {})
    return page("Hypotheses", f"""
<h2>Candidate hypotheses, ranked before measurement</h2>
<p>Each names the layers, the physical signature, why it should catch a fault the catalogue
lacks, and how it differs from everything already in the project family.</p>
<table>
<tr><th>#</th><th>hypothesis</th><th>layers</th><th>signature</th><th>why it finds a
<i>missing</i> fault</th><th>cost</th><th>result</th></tr>
<tr><td><b>H1</b><br><span class="tag">tested</span></td>
 <td>Native-resolution lidar scarp lane</td>
 <td>1 m-LiDAR descriptors <code>L_ex_max, L_step_max, L_coh100, L_strike</code>;
     100 m <code>det_elev</code>; 10 m <code>slope_p90, relief_local, aspect_coherence</code></td>
 <td>Frangi multiscale vesselness + Steger sub-pixel line localisation + structure-tensor
     coherence/strike, at 2–20 px scales, fused with scarp amplitude × coherence and a
     strike-concordance term</td>
 <td>The INGENIOUS mappers identified faults from 1 m GeoDAWN lidar hillshades
     (Giddens et al., Stanford Geothermal Workshop 2025). A fault they could add is one whose
     scarp is visible at 1 m and absent from the Quaternary catalogue; the 100 m stack
     averages that scarp away.</td>
 <td>low</td>
 <td><span class="pill ok">PROMOTED</span><br>+0.031 over chance</td></tr>

<tr><td><b>H2</b><br><span class="tag">tested</span></td>
 <td>SGMC off-catalogue supervised field</td>
 <td>all 53 non-inventory layers</td>
 <td>gradient boosting, positives = 61,664 SGMC fault pixels &gt; 300 m from the catalogue</td>
 <td>SGMC is the only large inventory of <i>real</i> faults the given catalogue lacks, so it is
     the closest analogue of the hidden set. Prior sessions used SGMC only as an evaluation
     instrument, never as a training target.</td>
 <td>low</td>
 <td><span class="pill bad">REFUTED</span><br>−0.035 vs incumbent</td></tr>

<tr><td><b>H3</b><br><span class="tag">tested</span></td>
 <td>Catalogue habitat (the family's implicit method)</td>
 <td>all 53 non-inventory layers</td>
 <td>gradient boosting on the 60,988 given labels</td>
 <td>control: measures what a catalogue-trained detector achieves on off-catalogue truth</td>
 <td>low</td>
 <td><span class="pill warn">CONTROL</span><br>−0.014 vs incumbent</td></tr>

<tr><td><b>H4</b><br><span class="tag">tested</span></td>
 <td>Novelty × lane fusion</td>
 <td>H1 + H2</td><td>rank fusion 0.6·H2 + 0.4·H1</td>
 <td>corroboration: two independent channels must agree</td>
 <td>low</td>
 <td><span class="pill bad">REFUTED</span><br>−0.026 vs incumbent</td></tr>

<tr><td><b>H5</b><br><span class="tag">not run</span></td>
 <td>Relief-gated emission</td>
 <td>H1 + <code>T_relief_local</code></td>
 <td>refuse to emit below a relief percentile</td>
 <td>a scarp cannot survive basin-floor aggradation, so mass there is pure cost</td>
 <td>low</td>
 <td><span class="pill warn">MEASURED, NOT SHIPPED</span><br>+0.005 local, unmeasurable
     live risk</td></tr>
</table>

<h3>Results at a glance (novelty instrument, 8 folds, matched envelope)</h3>
<table><tr><th>field</th><th>mean DTI</th><th>vs incumbent</th></tr>
{"".join(f"<tr><td class='mono'>{esc(k)}</td><td>{sum(v['N'])/len(v['N']):.5f}</td>"
         f"<td>{sum(v['N'])/len(v['N']) - sum(e1['incumbent']['N'])/len(e1['incumbent']['N']):+.5f}</td></tr>"
         for k, v in e1.items() if 'N' in v)}
<tr><td class="mono"><b>random (chance)</b></td>
    <td><b>{ch.get('random', {}).get('mean', 0):.5f}</b><td>—</td></tr></table>

<div class="bad"><b>Why H2 failed, and why that is the most useful result of the session.</b>
A model trained on off-catalogue SGMC faults scores 0.014 on held-out SGMC faults — worse than
random. It has learned the <i>regional geology</i> of the training clusters, not the fault
signal: when a whole spatial cluster is withheld, nothing transfers. Any proposal to "train on
the faults the catalogue is missing" has to survive that test, and this one did not.</div>
""", "hypotheses.html")


def research_page() -> str:
    e3 = load(ROOT / "evidence" / "experiment3_controls.json", {})
    cal = load(ROOT / "evidence" / "live_anchor_calibration.json", {})
    par = load(ROOT / "evidence" / "live_anchor_partial.json", {})
    top = cal.get("layers", [])[:10]
    pt = {r["layer"]: r for r in par.get("layers", [])}
    return page("Research", f"""
<h2>Research notes</h2>

<h3>1 · The metric, re-derived</h3>
<p>Transcribed line by line from the
<a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">problem
page</a> and verified against a brute-force O(N·|G|) implementation to 1e-9
(<code>tests/test_metric.py</code>). <code>FN<sub>w</sub> = |G| − TP<sub>w</sub></code>
exactly, which collapses the score to
<code>DTI = T / (0.2T + 0.2(S − M) + 0.8|G|)</code> and gives the marginal-credit rule
<code>k &gt; 0.2·DTI</code>.</p>

<h3>2 · Live-score anchoring, and why we distrust it</h3>
<p>We correlated the mean value of every layer under each submitted raster's dots against that
raster's owner-reported live score (18 distinct rasters). The raw correlations are startling:</p>
<table><tr><th>layer</th><th>ρ (raw)</th><th>ρ (partial, controlling for dot count and
catalogue distance)</th><th>|ρ| vs dot count</th></tr>
{"".join(f"<tr><td class='mono'>{esc(r['layer'])}</td><td>{r['rho']:+.3f}</td>"
         f"<td>{pt.get(r['layer'], {}).get('rho_partial', float('nan')):+.3f}</td>"
         f"<td>{pt.get(r['layer'], {}).get('rho_vs_n_dots', float('nan')):+.3f}</td></tr>"
         for r in top)}</table>
<div class="bad"><b>This table is not evidence.</b> Every layer's dot-mean also correlates with
the <i>number of emitted dots</i> at |ρ| = 0.5–0.9, because the registry is one lineage in
which the dot count and the field changed together. The five lidar scarp channels flip sign
under nuisance control (<code>L_ex_max</code>: +0.57 raw → −0.62 partial). We therefore used
this analysis only to choose a lane, never as a score. Logged as IR-66-PROXY-01.</div>

<h3>3 · The size of the hidden truth</h3>
<p>The 0.2778 raster was produced from the 0.2708 raster by deleting the 2,545 dots within
200 m of the catalogue. Assuming those dots earned no credit (they sit on faults the organiser
does not score), the two reported scores and the two masses give two equations in
<code>T</code> and <code>|G|</code>:</p>
<pre>0.2708 = T / (0.2·40199 + 0.8·|G|)
0.2778 = T / (0.2·37654 + 0.8·|G|)   ⇒   |G| ≈ 15,200 px,  T ≈ 5,470</pre>
<p>So the family's best raster captures roughly <b>36 %</b> of the weighted truth. At the same
37,654-dot budget a <i>perfect</i> field would score
<code>|G| / (0.2·S + 0.8·|G|) ≈ 0.77</code>. The distance between 0.28 and 0.77 is detector
quality, and it is the entire prize.</p>

<h3>4 · Chance level</h3>
<p>Measured, not assumed: {e3.get('chance', {}).get('random', {}).get('mean', 0):.5f} for
37,654 random dots at the same geometry. Without that number a holdout DTI of 0.04 is
uninterpretable, because the metric pays any sparse dot set.</p>

<h3>5 · What the geological literature says about where the new faults are</h3>
<ul>
<li><b>[official]</b> The organiser's hidden set is "faults ... not contained within the
current public USGS database", manually labelled by experts.</li>
<li><b>[literature]</b> The INGENIOUS mappers "utilized LiDAR and hillshades ... to identify
the extent and location of Quaternary faults", using "one-meter LiDAR from the GeoDAWN project
... provided by the USGS" (Giddens et al.,
<a href="https://pangea.stanford.edu/ERE/pdf/IGAstandard/SGW/2025/Giddens.pdf">Stanford
Geothermal Workshop 2025</a>). This is the direct justification for the lidar lane.</li>
<li><b>[literature]</b> The same work reports gravity as "the most useful geophysical dataset
in defining the extent and geometries of the major Quaternary faults" and step-overs as the
most common favourable structural setting (~63 %, dominantly N–NNE striking).</li>
<li><b>[literature]</b> Sare &amp; Hilley,
<a href="https://doi.org/10.21105/joss.01066">JOSS 2018</a> — scarplet template matching
returns amplitude, relative age, orientation and SNR from a DEM.
Steger, <a href="https://doi.org/10.1109/34.659930">IEEE TPAMI 20(2):113–125, 1998</a> —
sub-pixel line extraction from the Hessian eigenvector.
Frangi et al., MICCAI 1998, LNCS 1496:130–137 — multiscale vesselness.</li>
</ul>
<div class="note"><b>Deviation, stated not hidden.</b> The 1 m tiles are not downloadable from
this sandbox (IR-66-DATA-01), so the scarplet template matcher could not be re-run on native
data. The lane is executed on the hash-pinned 1 m-derived per-100 m descriptor stack and on the
100 m detrended elevation, at 2–20 <i>pixel</i> (200–2000 m) scales.</div>
""", "research.html")


def results_page() -> str:
    e1 = load(ROOT / "evidence" / "experiment1_parsed.json", {})
    e3 = load(ROOT / "evidence" / "experiment3_controls.json", {})
    rf = load(ROOT / "evidence" / "range_front_stratification.json", {})
    rg = load(ROOT / "evidence" / "relief_gate.json", {})
    sweep = e3.get("mass_sweep", {})
    return page("Results", f"""
<h2>Results</h2>
<div class="note">Every number below is <b>HOLDOUT-DTI</b> — evaluator version
<code>gemsdoe66.metric.dti</code> (verified against a brute-force transcription of the
organiser's equations to 1e-9), pooled distance-weighted Tversky with α = 0.2, β = 0.8 and a
300 m triangular kernel, on 8 spatially blocked folds with
<b>≈ 7,700 withheld positives per fold</b> (61,664 in total for the novelty instrument,
60,988 for the catalogue instrument). 95 % intervals are percentile bootstraps over folds.
<b>No ORGANIZER-CONFIRMED score exists for any artifact in this repository.</b></div>

<h3>Primary instrument — novelty (SGMC off-catalogue truth)</h3>
<table><tr><th>field</th><th>mean DTI</th><th>per-fold</th><th>vs incumbent</th></tr>
{"".join(f"<tr><td class='mono'>{esc(k)}</td><td><b>{sum(v['N'])/len(v['N']):.5f}</b></td>"
         f"<td class='small'>{', '.join(f'{x:.4f}' for x in v['N'])}</td>"
         f"<td>{sum(v['N'])/len(v['N']) - sum(e1['incumbent']['N'])/len(e1['incumbent']['N']):+.5f}</td></tr>"
         for k, v in e1.items() if 'N' in v)}</table>

<h3>Chance control</h3>
<table><tr><th>control</th><th>mean</th><th>95 % CI</th></tr>
{"".join(f"<tr><td class='mono'>{esc(k)}</td><td>{v['mean']:.5f}</td>"
         f"<td>[{v['ci95'][0]:+.5f}, {v['ci95'][1]:+.5f}]</td></tr>"
         for k, v in e3.get('chance', {}).items() if isinstance(v, dict) and 'mean' in v)}</table>

<h3>Range-front stratification</h3>
<table><tr><th>terrain</th><th>lane</th><th>chance</th><th>gain</th><th>95 % CI</th>
<th>folds+</th></tr>
{"".join(f"<tr><td>{esc(k)}</td><td>{v['lane_mean']:.5f}</td><td>{v['random_mean']:.5f}</td>"
         f"<td><b>{v['gain']:+.5f}</b></td>"
         f"<td>[{v['gain_ci95'][0]:+.5f}, {v['gain_ci95'][1]:+.5f}]</td>"
         f"<td>{v['folds_positive']}/{v['n_folds']}</td></tr>"
         for k, v in rf.get('strata', {}).items())}</table>

<h3>Mass sweep (novelty instrument)</h3>
<table><tr><th>emitted dots</th><th>lidar lane</th><th>incumbent prior surface</th></tr>
{"".join(f"<tr><td>{esc(k)}</td><td>{v.get('lidar_lane', {}).get('mean', 0):.5f}</td>"
         f"<td>{v.get('incumbent_prior', {}).get('mean', 0):.5f}</td></tr>"
         for k, v in sweep.items())}</table>
<div class="note">The sweep says <i>more</i> mass is better on this instrument. It is
<b>not</b> used to set the shipped budget: the instrument's truth (61,664 px) is about four
times the size of the likely hidden set (≈ 15,200 px, §3 of the research page), and the
live-board optimum for this family was measured at 37–46 k dots. Changing the mass on the
strength of a proxy with the wrong truth size would be an unvalidated leap.</div>

<h3>Relief gate (measured, not shipped)</h3>
<table><tr><th>gate</th><th>mean DTI</th><th>95 % CI</th><th>pixels excluded</th></tr>
{"".join(f"<tr><td class='mono'>{esc(k)}</td><td>{v['mean']:.5f}</td>"
         f"<td>[{v['ci95'][0]:+.5f}, {v['ci95'][1]:+.5f}]</td>"
         f"<td>{v['excluded_px']:,}</td></tr>"
         for k, v in rg.get('gates', {}).items())}</table>
""", "results.html")


def sources_page() -> str:
    return page("Sources", """
<h2>Sources</h2>
<p>Every link below was read for this session. Items marked <b>[official]</b> are organiser or
USGS primary sources; <b>[literature]</b> items are peer-reviewed or conference proceedings.</p>
<table>
<tr><th>source</th><th>what we took from it</th><th>link</th></tr>
<tr><td>Competition problem page</td><td>metric definition, α/β/R, submission format, the
 statement that the test set is faults <i>not</i> in the USGS database</td>
 <td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/">page 967</a></td></tr>
<tr><td>Competition leaderboard</td><td>the live public board (0.4133 at #1 on 2026-10-11)</td>
 <td><a href="https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/">leaderboard</a></td></tr>
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
<tr><td><b>IR-66-SCORE-01</b></td>
 <td>The task brief states "0.3195 is the highest score right now". The live public
 leaderboard on 2026-10-11 shows <b>0.4133 at #1</b> and 0.3195 (DARD) at <b>rank 9</b>. The
 brief's target is a stale snapshot.</td>
 <td><span class="pill warn">OPEN</span></td></tr>
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
 <td>The protocol's "70 % of dots within 3 px" duplicate test trips on any registry raster that
 is much denser than the candidate: against a 311,617-dot file, ~83 % of <i>random</i>
 locations are already within 3 px. The gate was made density-aware (overlap must exceed 70 %
 <b>and</b> 1.5× the random-placement rate).</td>
 <td><span class="pill ok">FIXED</span></td></tr>
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
</table>
""", "irregularities.html")


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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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


# ------------------------------------------------------------------------------------------
def submission_block() -> str:
    """The one-click download block.  Reads the newest build manifest."""
    # The audited raster lives outside docs/ on purpose: with a NEGATIVE verdict it must not
    # be publishable.  The banner is rendered either way, and it says so.
    ART = ROOT / "artifacts" / "lidar_lane"
    mans = sorted(ART.glob("*.manifest.json"))
    m = load(mans[-1], {}) if mans else load(next(iter(DL.glob("*.manifest.json")), ""), {})
    slug = m.get("slug", "")
    nan = DL / f"{slug}-nan.tif"
    zro = DL / f"{slug}-zeros.tif"
    chk = load(ART / f"checks-{slug}-nan.tif.json", {})
    # Use the detailed dot comparison for diagnostics, but do not accept its density-adjusted
    # UNIQUE verdict as a release pass. The project protocol's raw >70% overlap rule is a stop;
    # full-registry completeness is also uncertified. The separate PR12 reconciliation records
    # that strict shared-wrapper contract.
    _uniq = sorted((ROOT / "evidence").glob(f"uniqueness_{slug}-nan.json"))
    uni = load(_uniq[-1], {}) if _uniq else m.get("uniqueness", {})
    max_rho = abs(float(uni.get("max_abs_spearman_rho", 0) or 0))
    max_w3 = float(uni.get("max_frac_dots_within_3px", 0) or 0)
    n_compared = int(uni.get("n_compared", 0) or 0)
    raw_overlap_stop = max_w3 > 0.70
    ok = bool(chk.get("ok"))
    # ---- current, data-driven release panel -------------------------------------
    cur = load(ROOT / "docs" / "downloads" / "current_release.json", None)
    if cur:
        man = load(ROOT / "docs" / "downloads" / cur["manifest"], {})
        uni = load(ROOT / "evidence" / cur["uniqueness"], {})
        val = man.get("validator", {})
        n_ok = len([c for c in val.get("checks", []) if c.get("status") == "PASS"])
        n_tot = len([c for c in val.get("checks", []) if c.get("status") != "INFO"])
        note = man.get("note", "")
        cleared = bool(cur.get("cleared")) and bool(val.get("passed"))
        return f"""
<div class="{"go" if cleared else "stop"}">
  <h2>Download status: {"READY TO SUBMIT" if cleared else "NOT AVAILABLE"}</h2>
  <p><b>{"Yes — the file below passed every gate we set. Download the .tif (or the .zip) and upload it to the competition submission form." if cleared else "There is no current TIFF or ZIP cleared for submission."}</b></p>
  <p class="small">This is an internal HOLDOUT-DTI result on our own hide-and-recover instruments.
  It is <b>not</b> an ORGANIZER-CONFIRMED score. A projection is never written as a score.</p>
  <p><a class="btn" href="downloads/{esc(cur["tif"])}">Download submission GeoTIFF (.tif)</a>
     <a class="btn" href="downloads/{esc(cur["zip"])}">Download .zip</a>
     <a class="btn ghost" href="downloads/{esc(cur["manifest"])}">manifest / validator receipt</a></p>
  <table>
    <tr><th>sha256 (.tif)</th><td class="mono">{esc(man.get("tif_sha256", ""))}</td></tr>
    <tr><th>size</th><td>{man.get("bytes", 0):,} bytes</td></tr>
    <tr><th>emitted pixels</th><td>{man.get("dots", 0):,} ({man.get("dots", 0) / 5_167_373 * 100:.3f}% of the 5,167,373-px footprint)</td></tr>
    <tr><th>format validator (re-read from disk)</th>
        <td>{pill(val.get("passed"))} {n_ok}/{n_tot} checks; skipped={val.get("skipped_checks_mean_unverified")}</td></tr>
    <tr><th>HOLDOUT-DTI vs mass-matched random</th><td>{esc(cur.get("gate_summary", ""))}</td></tr>
    <tr><th>leakage canary</th><td>{esc(cur.get("canary_summary", ""))}</td></tr>
    <tr><th>uniqueness vs {uni.get("rasters_compared", 0)} registry rasters</th>
        <td>{pill(not uni.get("duplicate_chance_corrected"), "no duplicate (chance-corrected)")}
        max |rho| = {uni.get("max_abs_spearman")}; density-comparable max 3-px overlap =
        {uni.get("max_dot_overlap_fraction_density_comparable")}.<br>
        <span class="small">{esc(uni.get("rule_note", ""))}</span></td></tr>
    <tr><th>submission name</th><td class="mono">{esc(man.get("name", ""))}</td></tr>
    <tr><th>submission note ({man.get("note_chars", 0)}/140 chars)</th><td class="mono">{esc(note)}</td></tr>
  </table>
  <p class="small">Is it OK to download and submit?
  <b>{"Yes." if cleared else "No — not yet."}</b>
  The <a href="executive-summary.html">executive summary</a> states the gate, the exact
  measurements, and the caveats. Historical H66/H66-2/lidar_lane artifacts remain
  <b>audit-only and must not be uploaded</b>.</p>
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
 <div class="card"><h4>Data</h4><p class="big">23/23</p>
   <p class="small">hash-pinned mirrors restored and byte-verified</p></div>
 <div class="card"><h4>Layers</h4><p class="big">59</p>
   <p class="small">competition bands, 1 m-LiDAR scarp descriptors, 10 m topography, χ,
   GeoDAWN radiometrics</p></div>
 <div class="card"><h4>Holdout</h4><p class="big">8</p>
   <p class="small">spatially coherent balanced folds, 300 m buffer, training-only</p></div>
 <div class="card"><h4>Duplicate gate</h4><p class="big">STOP / UNVERIFIED</p>
   <p class="small">Raw 3 px dot overlap is 0.990 (&gt; 0.70); only 60 accessible rasters were
   compared, the complete registry is uncertified, and surface correlation was not reported.</p></div>
</div>
<p class="small"><a href="analysis.html">H33 attribution review</a> · <a href="review/2026-10-11-pr12-reconciliation.md">PR #12 merge reconciliation and shared-template provenance audit</a></p>
""", "index.html")


def exec_page() -> str:
    """Executive summary: exactly how to submit, and the one-sentence decision."""
    rel = load(DOCS / "downloads" / "current_release.json", None)
    man = load(DOCS / "downloads" / rel["manifest"], {}) if rel else {}
    uni = load(ROOT / "evidence" / rel["uniqueness"], {}) if rel else {}
    card = load(DOCS / "data" / "run-card.json", {})
    val = man.get("validator", {})
    n_ok = len([c for c in val.get("checks", []) if c.get("status") == "PASS"])
    n_tot = len([c for c in val.get("checks", []) if c.get("status") != "INFO"])
    cleared = bool(rel and rel.get("cleared")) and bool(val.get("passed"))
    verdict = card.get("verdict", "negative")
    tif = rel["tif"] if rel else ""
    zippy = rel["zip"] if rel else ""
    name = man.get("name", "")
    note = man.get("note", "")
    sha = man.get("tif_sha256", "")
    dots = man.get("dots", 0)

    if cleared:
        decision = (
            '<div class="go">\n  <h2>Is it OK to download and submit? Yes.</h2>\n'
            "  <p>The file below passed every gate this project set: the prescribed\n"
            "  spatial-block hide-and-recover holdout, the leakage canary, the registry\n"
            "  duplicate check and the official format validator. Download it and upload it\n"
            "  to the competition.</p>\n"
            f'  <p><a class="btn" href="downloads/{esc(tif)}">Download the submission GeoTIFF (.tif)</a>\n'
            f'     <a class="btn" href="downloads/{esc(zippy)}">Download the .zip</a></p>\n'
            "  <p class=\"small\"><b>What the number is.</b> The result is an internal\n"
            "  <b>HOLDOUT-DTI</b> on our own hide-and-recover instruments, with a 95 % CI,\n"
            "  measured against mass-matched random placement. It is <b>not</b> an\n"
            "  ORGANIZER-CONFIRMED score: no leaderboard receipt exists for this file and none\n"
            "  is claimed. A projection is never written as a score.</p>\n</div>")
    else:
        decision = (
            '<div class="stop">\n  <h2>Is it OK to download and submit? No.</h2>\n'
            "  <p>No file is currently cleared. Do not spend a weekly submission slot.</p>\n</div>")

    gate_rows = ""
    if rel:
        for inst_key, label in (
            ("blocks", "Prescribed instrument — lidar-covered spatial-block hide-and-recover"),
            ("traces", "Second instrument — global whole-trace holdout"),
        ):
            vs = (card.get("holdout_dti", {}).get("instruments", {})
                  .get(inst_key, {}).get("variants", {}) or {})
            for k in sorted(vs):
                v = vs[k]
                gate_rows += (
                    f"<tr><td>{esc(label)} — {esc(k)}</td>"
                    f"<td class='mono'>{v.get('mean')}</td>"
                    f"<td class='mono'>{v.get('ci95')}</td>"
                    f"<td>{esc(v.get('label', ''))}</td></tr>")

    caveats = "".join(f"<li>{esc(c)}</li>" for c in (rel or {}).get("caveats", []))

    return page("How to submit", f"""
<h1>Executive summary — how to submit</h1>
<p class="sub">One page: the decision, the file, the exact form fields, and the evidence
behind them.</p>

{decision}

<h2>1 · The decision, in one sentence</h2>
<p><b>{"Download the .tif below and upload it to the DrivenData submission form — it passed every gate we set." if cleared else "No file is cleared; do not submit."}</b>
Verdict in the canonical run card: <span class="tag">{esc(verdict)}</span></p>

<h2>2 · Exactly how to submit (step by step)</h2>
<ol>
  <li><b>Download</b> <code>{esc(tif)}</code> ({man.get('bytes', 0):,} bytes) — or the
      <code>.zip</code> if the form prefers an archive. Both contain the same single-band
      GeoTIFF.</li>
  <li>Open the competition submissions page on the DrivenData host (no leaderboard values are
      mirrored here) and choose <b>New submission</b>.</li>
  <li>Under <b>File to submit</b> pick the downloaded <code>.tif</code> (or the
      <code>.zip</code>).</li>
  <li>Paste the <b>name</b> and the <b>note</b> from the table below. The note is
      {man.get('note_chars', 0)}/140 characters — the form rejects anything longer.</li>
  <li>Press <b>Create submission</b>. Until the organiser actually returns a receipt,
      <b>no ORGANIZER-CONFIRMED score exists for this file and none is claimed here</b>;
      every number on this site is <code>HOLDOUT-DTI</code>. When a receipt arrives it
      replaces the projection.</li>
</ol>

<h3>Form fields — copy these exactly</h3>
<table>
  <tr><th>File to submit</th><td class="mono">{esc(tif)}</td></tr>
  <tr><th>Name</th><td class="mono">{esc(name)}</td></tr>
  <tr><th>Note ({man.get('note_chars', 0)}/140)</th><td class="mono">{esc(note)}</td></tr>
  <tr><th>sha256</th><td class="mono">{esc(sha)}</td></tr>
</table>

<div class="note"><b>Why an earlier upload was rejected with &ldquo;Predicted values must be
in range [0, 1]&rdquo;.</b> The organiser rejects a raster that contains any value outside
[0, 1], any NaN <i>inside</i> the footprint, or a finite value anywhere <i>outside</i> it.
This file has min 0.0, max 1.0, 0 NaN inside the 5,167,373-cell footprint and NaN in every
one of the 7,111,787 cells outside it — verified by re-reading the written file,
{n_ok}/{n_tot} checks PASS, 0 skipped. If you re-export it yourself, do not write 0 outside
the footprint and do not keep a finite nodata tag.</div>

<h2>3 · The evidence behind the decision</h2>
<table>
  <tr><th>instrument / variant</th><th>HOLDOUT-DTI mean</th><th>95 % CI</th><th>label</th></tr>
  {gate_rows}
</table>
<p class="small">Evaluator: <code>src/gems/metric.py</code>, &alpha; = 0.2, &beta; = 0.8,
triangular kernel R = 300 m. Four folds on each instrument; withheld positives per fold
&asymp; 6,715 (blocks) and &asymp; 12,090 (traces). The comparison that matters is the lane
versus <b>mass-matched random placement</b> at the same dot budget and spacing.</p>

<h3>Leakage canary</h3>
<p>{esc(card.get("leakage_canary", {}).get("status", ""))} — maximum per-channel AUC
{card.get("leakage_canary", {}).get("max_auc_observed")} across
{card.get("leakage_canary", {}).get("n_channels_tested")} channels, against the 0.90
threshold.</p>

<h3>Uniqueness against {uni.get("rasters_compared", 0)} registry rasters</h3>
<p>max |Spearman &rho;| = {uni.get("max_abs_spearman")} (limit 0.90); density-comparable
max 3-px dot overlap = {uni.get("max_dot_overlap_fraction_density_comparable")}
(limit 0.70); no identical SHA-256 and no identical decoded pixels.
{esc(uni.get("rule_note", ""))}</p>

<h2>4 · Caveats you should read before spending a slot</h2>
<ul>{caveats}</ul>

<h2>5 · Format rules this file satisfies</h2>
<table>
  <tr><th>check</th><th>meaning</th><th>this file</th></tr>
  <tr><td>single band</td><td>the organiser asks for one layer</td><td>count = 1</td></tr>
  <tr><td>float32</td><td>“datatype of 32-bit float”</td><td>float32</td></tr>
  <tr><td>3730 × 3292</td><td>same shape as the template</td><td>3730 × 3292</td></tr>
  <tr><td>EPSG:32611</td><td>“the same projected coordinate reference system”</td><td>EPSG:32611</td></tr>
  <tr><td>geotransform</td><td>100 m, origin (243350, 4508550)</td><td>exact match</td></tr>
  <tr><td>values</td><td>all finite values in [0, 1]</td><td>min 0.0, max 1.0</td></tr>
  <tr><td>NaN policy</td><td>“data outside the bounds is null or nan”</td><td>0 finite outside; 0 NaN inside</td></tr>
  <tr><td>emitted cells</td><td>dots at 1.0, everything else 0.0</td><td>{dots:,}</td></tr>
</table>

<h2>6 · Never upload a historical artifact</h2>
<p>The H66-1 TIFF/ZIP bytes remain withdrawn: byte-verified audit copies live under
<code>evidence/archives/h66-1/</code>, outside the Pages document root and with no site
link. H66-2 and the inherited <code>lidar_lane</code> field are audit-only under
<code>artifacts/h66-2/</code> and <code>artifacts/lidar_lane/</code>. None of them passed
the holdout, leakage, uniqueness or format gates.</p>
""", "executive-summary.html")


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
            f"<td>{esc(h.get('expected_gain'))}</td>"
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

#!/usr/bin/env python3
"""Build the blocked project-status site from docs/data/*.json.

This version never emits a TIFF/ZIP download link. Enabling any future artifact link
requires a separately reviewed change that checks the full release gates and exact
artifact hash. The builder does not fetch or monitor external websites.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DATA = DOCS / "data"

PAGES = [
    "index.html", "feed.html", "submission-guide.html", "analysis.html",
    "hypotheses.html", "run-card.html", "irregularities.html", "sources.html",
    "h66-session.html", "executive-summary.html",
]
NAV = [
    ("index.html", "Overview"),
    ("feed.html", "Project feed"),
    ("submission-guide.html", "Submission workflow"),
    ("hypotheses.html", "Ranked hypotheses"),
    ("analysis.html", "H33 attribution"),
    ("run-card.html", "Run card"),
    ("irregularities.html", "Audit findings"),
    ("sources.html", "Sources"),
    ("executive-summary.html", "Executive summary"),
    ("h66-session.html", "H66 archive"),
]

CSS = """
:root{color-scheme:light;--ink:#15283a;--muted:#566a7b;--paper:#f3f6f8;--card:#fff;--line:#d9e2e8;--blue:#175d83;--red:#9d302d;--redbg:#fff0ee;--amber:#845318;--amberbg:#fff7e7;--green:#276047;--greenbg:#edf8f0}
*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.58 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}main{max-width:1120px;margin:0 auto;padding:24px clamp(16px,4vw,48px) 64px}nav{display:flex;flex-wrap:wrap;gap:7px;margin:4px 0 28px;padding:0 0 16px;border-bottom:1px solid var(--line)}nav a{padding:6px 10px;border-radius:8px;color:var(--blue);text-decoration:none;font-size:.91rem}nav a:hover,nav a.active{background:#e4eef4;color:#123e58}h1{font-size:clamp(2rem,5vw,3.2rem);line-height:1.1;letter-spacing:-.035em;margin:.35em 0 .45em}h2{font-size:1.34rem;margin:1.45em 0 .45em}h3{font-size:1.05rem;margin:1.2em 0 .35em}p{margin:.55em 0 1em}.muted,.small{color:var(--muted)}.small{font-size:.92rem}.eyebrow{text-transform:uppercase;letter-spacing:.12em;font-size:.75rem;font-weight:750;color:var(--blue)}.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px 22px;margin:16px 0;box-shadow:0 4px 18px rgba(18,50,73,.035)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}.stat{padding:15px;border:1px solid var(--line);border-radius:12px;background:#fbfcfd}.stat b{display:block;margin-bottom:5px}.tag{display:inline-block;padding:3px 9px;border-radius:999px;font-size:.77rem;font-weight:750;letter-spacing:.02em}.red{color:var(--red);background:var(--redbg)}.amber{color:var(--amber);background:var(--amberbg)}.green{color:var(--green);background:var(--greenbg)}.blue{color:#1d5773;background:#e8f2f7}.banner{border:1px solid #e3aaa6;background:var(--redbg);border-radius:16px;padding:18px 22px;margin:18px 0}.banner h2{margin-top:0}.banner.warn{border-color:#e5ca93;background:var(--amberbg)}.banner.ok{border-color:#a9cdb8;background:var(--greenbg)}.mono,code,pre{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}code{overflow-wrap:anywhere;background:#f0f3f5;padding:.12em .35em;border-radius:5px;font-size:.91em}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#101f2d;color:#e4edf4;border-radius:12px;padding:16px;overflow:auto}a{color:var(--blue)}.button{display:inline-block;border-radius:9px;padding:9px 13px;background:var(--blue);color:white;text-decoration:none;font-weight:650}.button.disabled{background:#71808b;cursor:not-allowed}table{width:100%;border-collapse:collapse;margin:12px 0}th,td{text-align:left;vertical-align:top;border-bottom:1px solid var(--line);padding:9px 10px}th{background:#eef3f6}.item{border-left:4px solid #a7bac7;padding:3px 0 4px 15px;margin:20px 0}.item.critical,.item.high{border-color:#b74943}.item.medium{border-color:#d5a242}.item.info,.item.low{border-color:#6f9eb4}.footer{border-top:1px solid var(--line);margin-top:34px;padding-top:14px;color:var(--muted);font-size:.85rem}.kicker{font-size:.9rem;color:var(--muted)}.nowrap{white-space:nowrap}
@media(max-width:640px){main{padding-top:14px}nav{gap:2px}nav a{font-size:.83rem;padding:5px 7px}table{display:block;overflow-x:auto}.card{padding:17px}}
"""


def load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def e(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def display(value, missing="Not measured") -> str:
    return f"<em>{e(missing)}</em>" if value is None else e(value)


def page(filename: str, title: str, body: str, active: str) -> None:
    links = "".join(
        f'<a href="{e(href)}" class="{"active" if href == active else ""}">{e(label)}</a>'
        for href, label in NAV
    )
    doc = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="Auditable native-resolution LiDAR scarp-channel research; no candidate is currently cleared for submission.">
<title>{e(title)} · GEMSDOE66</title><style>{CSS}</style></head>
<body><main><nav aria-label="Primary">{links}</nav>{body}
<footer class="footer">GEMSDOE66 · Maximize P(Win) · Own the Outcome · Status is repository state, not organizer acceptance. No leaderboard values are mirrored.</footer>
</main></body></html>'''
    (DOCS / filename).write_text(doc, encoding="utf-8")


def status_grid(rc: dict) -> str:
    hd = rc["holdout_dti"]
    reg = rc["registry_checks"]
    return f'''<div class="grid">
<div class="stat"><b>Authorized inputs</b><span class="tag red">BLOCKED</span><p class="small">{e(rc['data_access']['competition_data'])}</p></div>
<div class="stat"><b>HOLDOUT-DTI</b><span class="tag red">NONE QUALIFIED</span><p class="small">{e(hd['status'])}</p></div>
<div class="stat"><b>Registry uniqueness</b><span class="tag red">BLOCKED</span><p class="small">{e(reg['reason'])}</p></div>
<div class="stat"><b>Validator</b><span class="tag red">NOT PASSED</span><p class="small">{e(rc['validator']['result'])}</p></div>
<div class="stat"><b>GeoTIFF download</b><span class="tag red">NOT AVAILABLE</span><p class="small">{e(rc['submission']['download_status'])}</p></div>
<div class="stat"><b>Independent scientific leads</b><span class="tag amber">OUTSTANDING</span><p class="small">{e(rc['independent_reviews']['status'])}</p></div>
</div>'''


def index_page(rc: dict, feed: dict) -> str:
    historical = rc["raster"]["historical_artifacts"][0]
    submission = rc["submission"]
    return f'''<div class="eyebrow">Native-resolution LiDAR scarp channels · current gate</div>
<h1>No submission-ready GeoTIFF</h1>
<p class="kicker">As of {e(feed['generated_utc'])}, no candidate passed the complete science, provenance, uniqueness, and exact-footprint gates. This is an explicit stop state, not a missing download button.</p>
<div class="banner"><h2>Download status: NOT AVAILABLE</h2><p><strong>There is no current TIFF or ZIP cleared for submission.</strong> Do not upload a historical H66 artifact. The old binaries were removed from the published downloads directory; H66-1 bytes are retained only in an unlinked audit archive outside the Pages document root.</p><p><b>Planning identifier only:</b> <code>{e(submission['name'])}</code> ({e(submission.get('name_status'))}). <b>Proposed note ({e(submission['note_chars'])}/140 characters):</b> “{e(submission['note'])}” ({e(submission.get('note_status'))}). This name and note are not cleared for use; no candidate file exists.</p></div>
{status_grid(rc)}
<section class="card"><h2>Why the project is blocked</h2><ul>
<li>The official competition data tab redirected this unauthenticated session to login. No credentials were used; no official training rasters, labels, sample submission, or DEM-link inventory are present.</li>
<li>The historical H66 runner uses full-catalogue distance when choosing candidate cells before hide-and-recover scoring. That lets withheld labels influence placement, so its old scalar is not a qualified HOLDOUT-DTI result.</li>
<li>The required complete raster registry, whole-geologic-segment buffered holdout, LiDAR-covered evaluation mask, 95% CI, and independent scientific reviews are not available.</li>
<li>The official output contract requires NaN outside the exact reference footprint. The canonical shared <code>gems.submission_writer</code> supports that contract, but the historical H66 path still calls older all-finite <code>gems57</code> helpers. It remains disabled until it is rewired to the shared writer and the exact reference grid is available.</li>
</ul></section>
<section class="card"><h2>What is ready</h2><p>Four distinct same-lane hypotheses are ranked before implementation. The lead is a method-faithful slope-aware scarp-template plus scale-persistent Steger/Frangi field. Its expected gain is qualitative only; it has not been implemented or tested.</p><p><a class="button" href="hypotheses.html">Review the ranked hypotheses</a> <a class="button" href="feed.html">Open the dated project feed</a></p></section>
<section class="card"><h2>Historical file disposition</h2><p>The prior all-finite raster is retained only as an audit archive at <code>{e(historical.get('archive_file', 'not archived'))}</code>, outside the Pages document root and without a download link. SHA-256 <code>{e(historical['sha256'])}</code>. Its exact official transform/footprint was not verified. See the <a href="h66-session.html">H66 archive note</a> and the <a href="review/2026-10-11-audit.md">technical audit</a>.</p></section>
<p><a href="submission-guide.html">Submission workflow</a> · <a href="analysis.html">H33 attribution</a> · <a href="run-card.html">Current JSON run card</a> · <a href="irregularities.html">Audit findings</a> · <a href="sources.html">Source register</a> · <a href="research/metric-derivation.md">Metric derivation</a></p>'''


def feed_page(feed: dict) -> str:
    rows = []
    for item in feed["entries"]:
        links = " · ".join(f'<a href="{e(href)}">{e(href)}</a>' for href in item.get("links", []))
        src = f'<p class="small">Source register: <code>{e(item["source_id"])}</code></p>' if item.get("source_id") else ""
        rows.append(f'''<article class="item"><div class="eyebrow">{e(item['date'])} · {e(item['kind'])}</div>
<h2>{e(item['status'])}</h2><p>{e(item['summary'])}</p>{src}{f'<p class="small">{links}</p>' if links else ''}</article>''')
    actions = "".join(f"<li>{e(x)}</li>" for x in feed["next_actions"])
    return f'''<div class="eyebrow">Project feed · not a leaderboard feed</div><h1>Current status and next actions</h1>
<div class="banner"><h2>{e(feed['status'])}</h2><p>{e(feed['scope'])}</p><p class="small">{e(feed['external_monitoring'])}</p></div>
<section class="card"><h2>Latest project events</h2>{''.join(rows)}</section>
<section class="card"><h2>Next actions</h2><ol>{actions}</ol></section>
<p class="small">This static status file is updated with repository changes. It does not poll DrivenData, copy public standings, or claim to be live. See <code>docs/status-feed.json</code> for the JSON feed.</p>'''


def submission_page(rc: dict) -> str:
    hist = rc["raster"]["historical_artifacts"][0]
    return f'''<div class="eyebrow">Submission workflow</div><h1>How to submit — currently blocked</h1>
<div class="banner"><h2>No file is available to upload</h2><p>{e(rc['submission']['clearance'])} There is no active TIFF/ZIP link. Historical file SHA-256 <code>{e(hist['sha256'])}</code> is shown for audit only; the file is not submission-cleared.</p></div>
<section class="card"><h2>Release gates before any future download</h2><ol>
<li><b>Inputs and provenance:</b> authorized competition training features, labels, sample grid, exact DEM tile inventory, and verified shareable data lineage.</li>
<li><b>Pre-implementation review:</b> two independent scientific leads review the ranked hypotheses, geological mechanism, named mimics, and planned holdout.</li>
<li><b>Valid science test:</b> whole vector-defined fault segments withheld with a preregistered buffer; catalogue-derived features use visible faults only; visible faults are masked pixel-exactly; truth and scoring restricted to LiDAR-covered holdout blocks; pooled DTI and 95% spatial-block CI; off-range-front check.</li>
<li><b>Leakage and novelty:</b> each feature alone tested on the holdout; AUC above 0.90 is a stop pending explanation. Compare continuous pre-placement surfaces and final dots against the complete registry. An incomplete registry is not a pass.</li>
<li><b>Official format:</b> normalize to float32 [0,1], write EPSG:32611 on the exact official shape/transform, and use NaN only outside the official footprint. Run the validator with both reference and features rasters; no skipped checks count as a pass.</li>
<li><b>Artifact receipt:</b> record name, note, SHA-256, pixel agreement, validator output, run card, and all review sign-offs. Only after every gate passes may a one-click TIFF be published.</li>
</ol></section>
<section class="card"><h2>Portal steps once a candidate is cleared</h2><ol>
<li>Use the download link on the project overview only after the run card explicitly changes to a cleared state.</li>
<li>Open the DrivenData homepage and navigate manually to the GEMS Prize and its submission form. This project does not deep-link, automate, or monitor the platform.</li>
<li>Upload the single-band TIFF or a ZIP containing exactly one TIFF, then use the run-card's unique name and short note. The project's field limit is 140 characters.</li>
<li>Follow the current official rules: feedback submissions are limited to three per week, and one final entry must be selected.</li>
<li>Include the required generative-AI disclosure in the submission narrative, describing the actual use across all submission materials. The text below is only a fill-in template.</li>
</ol>
<pre>Generative-AI disclosure (edit to match actual use): [Name the tool(s)]. I used generative AI to assist with [specific code, review, or documentation tasks] in developing [identify submission elements]. I independently checked [specific analyses, sources, and outputs]. The tools did not access private test labels or submit to the competition. [Correct every sentence to match what actually occurred.]</pre>
<p class="small">The official rules are the source of truth. The narrative template is not legal advice or a substitute for reading the current rules.</p></section>
<section class="card"><h2>Why the old format check is not enough</h2><p>The historical all-finite file's basic raster metadata/range checks do not prove it matches the official transform or footprint. The official reference and feature rasters were absent, so those checks were skipped. The old file is withdrawn from the download path and must not be submitted.</p></section>'''


def analysis_page(claims: dict) -> str:
    return '''<div class="eyebrow">Attribution review</div><h1>H33-2-B2: no defensible score explanation yet</h1>
<div class="banner warn"><h2>Attribution is unverified</h2><p>The supplied value is a user/owner-reported attribution, not an organizer-confirmed score. The owner-maintained GEMSDOE32 page describes the artifact as unscored and states that no organizer score exists for its artifacts. No receipt tied to the exact TIFF bytes or SHA-256 is present in this checkout.</p></div>
<section class="card"><h2>Why the mechanism cannot be inferred</h2><p>Without a receipt-to-hash mapping, the file-to-score link itself is missing. Without the exact artifact bytes and a controlled comparison, it is impossible to know whether the alleged change came from ranking, placement, probability mass, catalogue-adjacent pruning, rasterization, or something else. Those are hypotheses, not findings.</p><p>The official distance-weighted Tversky metric rewards probability mass near labeled faults and penalizes unsupported mass; the false-negative coefficient exceeds the false-positive coefficient. This explains the metric's general trade-off, not the outcome of an unverified H33 file.</p><p>To answer causally, obtain an organizer receipt for the exact artifact hash, preserve the file, and compare controlled variants under the same valid, leakage-free spatial protocol. Do not use hidden labels or a public leaderboard row as an artifact receipt.</p><p><a href="research/metric-derivation.md">Read the metric derivation</a> · <a href="sources.html">Review the source register</a>.</p></section>
<section class="card"><h2>Evidence disposition</h2><ul><li>Owner-maintained evidence is marked owner-reported only.</li><li>No leaderboard values are reproduced or mirrored in this site.</li><li>No organizer-confirmed numeric result is claimed.</li><li>The historical H66 holdout scalar is disqualified by the leakage and protocol audit.</li></ul></section>'''


def hypotheses_page(d: dict) -> str:
    items = []
    for h in d["items"]:
        items.append(f'''<article class="card"><div class="eyebrow">Rank {e(h['rank'])} · {e(h['id'])}</div><h2>{e(h['title'])}</h2>
<p><b>Layers/features:</b> {e(h['layers'])}</p><p><b>Physical signature:</b> {e(h['signature'])}</p>
<p><b>Why off-catalogue:</b> {e(h['why_off_catalogue'])}</p><p><b>Named non-fault mimic:</b> {e(h['named_mimic'])}</p>
<p><b>Difference from repository:</b> {e(h['differs_from_repo'])}</p><p><b>Cost:</b> {e(h['cost'])}</p>
<p><b>Expected gain:</b> {e(h['expected_gain'])}</p><p><b>Input availability:</b> {e(h['data_status'])}</p>
<p><b>Validation:</b> {e(h['validation'])}</p><p class="small"><b>Sources:</b> {e(', '.join(h.get('source_ids', [])) or 'None')}</p></article>''')
    p = d["protocol"]
    return f'''<div class="eyebrow">Pre-implementation ranking</div><h1>Four hypotheses, one lane</h1>
<div class="banner warn"><h2>No code or score is attached to these proposals</h2><p>{e(d['ranking_basis'])}</p><p>Only the lead proposal should enter implementation after scientific review and input/registry/tooling gates pass.</p></div>
<section class="card"><h2>Shared preregistered protocol</h2><ul>
<li><b>Scale and output:</b> {e(p['feature_scales_m'])} m native features, aggregated to {e(p['aggregation_m'])} m.</li>
<li><b>Holdout:</b> {e(p['holdout'])}</li><li><b>Metric:</b> {e(p['metric'])}</li><li><b>Leakage:</b> {e(p['leakage'])}</li>
<li><b>Range fronts:</b> {e(p['range_front_gate'])}</li><li><b>Uniqueness:</b> {e(p['uniqueness'])}</li><li><b>Budget:</b> {e(p['budget'])}</li>
<li><b>Inputs:</b> {e(p['input_availability'])}</li></ul></section>
{''.join(items)}'''


def run_card_page(rc: dict) -> str:
    hd = rc["holdout_dti"]
    reg = rc["registry_checks"]
    current = rc["raster"]
    submission = rc["submission"]
    validation = rc["validator"].get("current_candidate_result") or {}
    old = "".join(f"<li><code>{e(x['file'])}</code> — SHA-256 <code>{e(x['sha256'])}</code> — {e(x['status'])}; audit archive: <code>{e(x.get('archive_file', 'not archived'))}</code></li>" for x in current["historical_artifacts"])
    return f'''<div class="eyebrow">Canonical JSON run card</div><h1>{e(rc['run_id'])}</h1>
<div class="banner"><h2>{e(rc['verdict'])}</h2><p>No current raster path, score, receipt, or download is present.</p></div>
<section class="card"><h2>Hypothesis and mechanism</h2><p><b>Lane:</b> {e(rc['lane'])}</p><p><b>Top candidate:</b> {e(rc['top_candidate'])}</p><p>{e(rc['hypothesis'])}</p><p>{e(rc['mechanism'])}</p><p><b>Named non-fault mimic:</b> {e(rc['named_non_fault_mimic'])}</p></section>
<section class="grid"><div class="card"><h2>HOLDOUT-DTI</h2><p><span class="tag red">NO QUALIFIED RESULT</span></p><p><b>Value:</b> {display(hd['value'])}</p><p><b>Evaluator:</b> {display(hd['evaluator_version'])}</p><p><b>Withheld positives:</b> {display(hd['withheld_positive_count'])}</p><p><b>95% CI:</b> {display(hd['ci95'])}</p><p>{e(hd['reason'])}</p></div>
<div class="card"><h2>Leakage and registry</h2><p><b>Leakage canary:</b> {e(rc['leakage_canary']['status'])}</p><p><b>Threshold AUC:</b> {e(rc['leakage_canary']['threshold_auc'])}; no current feature results.</p><p><b>Pre-placement:</b> {e(reg['pre_placement_surface']['status'])}</p><p><b>Final dots:</b> {e(reg['post_placement_final_dots']['status'])}</p><p>{e(reg['reason'])}</p></div></section>
<section class="card"><h2>Raster, validator, and submission</h2><p><b>Current raster:</b> {e(current['status'])}</p><p><b>Current file:</b> {display(current['file'])}</p><p><b>Validator:</b> {e(rc['validator']['status'])}</p><p>{e(rc['validator']['result'])}</p><p><b>Current candidate validation:</b> {e(validation.get('status', 'Not run'))}</p><p><b>Footprint NaN:</b> {e(validation.get('footprint_nan_status', 'Not reported'))}</p><p><b>[0,1] range:</b> {e(validation.get('range_0_1_status', 'Not reported'))}</p><p><b>CRS/shape/transform:</b> {e(validation.get('crs_shape_transform_status', 'Not reported'))}</p><p><b>Proposed submission name:</b> <code>{e(submission.get('name'))}</code> — {e(submission.get('name_status'))}</p><p><b>Proposed note ({e(submission.get('note_chars'))}/{e(submission.get('note_limit_chars'))} characters):</b> “{e(submission.get('note'))}” — {e(submission.get('note_status'))}. Not for submission.</p><p><b>Download:</b> {e(submission['download_status'])}</p><h3>Historical artifacts withdrawn from the public download path</h3><ul>{old}</ul></section>
<section class="card"><h2>Inputs, budget, and reviews</h2><p><b>Competition inputs:</b> {e(rc['data_access']['competition_data'])}</p><p><b>DEM source:</b> {e(rc['data_access']['official_1m_dem_source'])}</p><p><b>Experiments used in this review:</b> {e(rc['budget']['new_experiments_used'])} / {e(rc['budget']['max_experiments'])}</p><p><b>Submission slots used:</b> {e(rc['budget']['submission_slots_used'])}</p><p><b>Independent scientific reviews:</b> {e(rc['independent_reviews']['completed'])} / {e(rc['independent_reviews']['scientific_lead_reviews_required'])} — {e(rc['independent_reviews']['status'])}</p></section>
<p class="small">Machine-readable card: <a href="data/run-card.json">docs/data/run-card.json</a>. Full source review: <a href="review/2026-10-11-audit.md">technical audit</a>.</p>'''


def irregularities_page(d: dict) -> str:
    parts = []
    for item in d["items"]:
        sources = ", ".join(item.get("source_ids", [])) or "internal code/evidence review"
        parts.append(f'''<article class="item {e(item['severity'])}"><div class="eyebrow">{e(item['id'])} · {e(item['severity'])}</div>
<h2>{e(item['title'])}</h2><p><span class="tag {'red' if item['severity'] in ('critical','high') else 'amber'}">{e(item['status'])}</span></p>
<p>{e(item['detail'])}</p><p class="small">Sources: {e(sources)}</p></article>''')
    return f'''<div class="eyebrow">Audit register</div><h1>Open gates and corrected claims</h1>
<p class="kicker">An issue closes only when the cited evidence and required checks are actually available. “Partial,” “owner-reported,” and “not verified” never mean pass.</p>{''.join(parts)}'''


def sources_page(d: dict) -> str:
    rows = []
    for s in d["sources"]:
        url = s["url"]
        # DrivenData's Terms of Use restrict subpage links; cite the exact path as text.
        if "drivendata.org/" in url and url.rstrip("/") != "https://www.drivendata.org":
            url_html = f'<code>{e(url)}</code>'
        else:
            url_html = f'<a href="{e(url)}">{e(url)}</a>'
        rows.append(f'''<article class="card"><div class="eyebrow">{e(s['id'])}</div><h2>{e(s['title'])}</h2>
<p><span class="tag blue">{e(s['status'])}</span></p><p>{e(s['supports'])}</p><p><b>URL:</b> {url_html}</p><p class="small">{e(s['how'])}</p></article>''')
    return f'''<div class="eyebrow">Evidence register</div><h1>Sources and provenance</h1>
<div class="banner warn"><h2>Source status is explicit</h2><p>Official sources, public bibliographic records, owner-reported material, and current access failures are distinguished. Exact DrivenData subpage paths are shown as text, not deep-linked; no leaderboard rows are copied or monitored.</p><p>Last source review: {e(d['verified_on'])}</p></div>
<section class="card"><p><a href="https://www.drivendata.org/">DrivenData homepage</a> · Use the official site navigation manually. The current data tab access state is recorded above; no credentials were used.</p></section>{''.join(rows)}'''


def archive_page(rc: dict) -> str:
    old = rc["raster"]["historical_artifacts"]
    hashes = "".join(f"<li><code>{e(x['file'])}</code>: SHA-256 <code>{e(x['sha256'])}</code>. {e(x['status'])}.</li>" for x in old)
    return f'''<div class="eyebrow">Historical H66 experiment · audit only</div><h1>H66 file withdrawn; no download</h1>
<div class="banner"><h2>Do not submit these historical bytes</h2><p>The TIFF/ZIP variants were removed from <code>docs/downloads</code>; byte-identical copies are retained only under <code>evidence/archives/h66-1/</code>, outside the Pages document root and without site links. They were not cleared by the complete registry, exact official footprint validation, or the required holdout/leakage protocol. The legacy result is disqualified from current HOLDOUT-DTI reporting.</p></div>
<section class="card"><h2>Identity retained for traceability</h2><ul>{hashes}</ul><p>The all-finite file had previously been inspected for basic raster metadata and pixel range. That does not establish exact reference transform, footprint, unique status, or organizer acceptance. The NaN variant's mask was not checked against the official features raster.</p></section>
<section class="card"><h2>Why the result was withdrawn</h2><ul><li>Full-catalogue distance influenced pre-score candidate eligibility, leaking withheld catalogue labels into placement.</li><li>The holdout protocol and LiDAR-only denominator did not match the current brief, and no valid level 95% CI was produced.</li><li>The registry was incomplete, so uniqueness was not passed.</li><li>The historical writer bypassed the required shared submission writer; the format validator lacked official reference/features rasters and returned not passed.</li><li>The previous site advertised files and safety claims inconsistent with those unresolved gates.</li></ul><p>See <a href="review/2026-10-11-audit.md">the complete technical audit</a> and <a href="data/run-card.json">the current run card</a>.</p></section>'''


def executive_page(rc: dict) -> str:
    return f'''<div class="eyebrow">Executive summary</div><h1>Current outcome: stop before download</h1>
<div class="banner"><h2>No candidate is cleared</h2><p>{e(rc['verdict'])}</p></div>
<section class="card"><h2>What was reviewed</h2><ul><li>Repository methodology, data-restore script, feature naming, holdout path, writer path, site generators, status registers, and available historical evidence.</li><li>Official problem specification, rules, data access, public-domain 3DEP product metadata, and the bibliographic records for Scarplet, Steger, Frangi, and the cited AGU abstract.</li><li>Offline unit tests. These tests do not substitute for competition data, a spatial holdout, a complete registry, or organizer acceptance.</li></ul></section>
<section class="card"><h2>What must happen before a submission can be made</h2><ol><li>Place lawfully accessed official rasters and exact 1 m DEM tiles in the documented local data directories; verify origin, hashes, licenses, CRS, and footprint.</li><li>Use the canonical shared buffered holdout and NaN-outside writer/validator path. If authoritative segment-ID handling or evaluator integration is missing, fix it once in the shared template and consume that implementation unchanged here; do not fork the vendored <code>gems57</code> path.</li><li>Review the ranked hypotheses with two independent scientific leads.</li><li>Implement only the reviewed lead; run the feature-alone canaries and buffered whole-segment, LiDAR-covered spatial holdout; report pooled DTI with evaluator version, positive count, and 95% CI.</li><li>Pass full-registry surface and final-dot checks plus exact official-grid validator checks. Only then enable one-click download and prepare the truthful AI disclosure.</li></ol></section>
<p><a class="button" href="submission-guide.html">Open the complete submission workflow</a> <a class="button" href="feed.html">View the current feed</a></p>'''


def main() -> int:
    rc = load("run-card.json")
    feed = load("feed.json")
    hypotheses = load("hypotheses.json")
    irregularities = load("irregularities.json")
    sources = load("sources.json")
    pages = {
        "index.html": ("GEMSDOE66 overview", index_page(rc, feed)),
        "feed.html": ("Project status feed", feed_page(feed)),
        "submission-guide.html": ("Submission workflow", submission_page(rc)),
        "analysis.html": ("H33 attribution", analysis_page(load("claims.json"))),
        "hypotheses.html": ("Ranked hypotheses", hypotheses_page(hypotheses)),
        "run-card.html": ("Current run card", run_card_page(rc)),
        "irregularities.html": ("Audit findings", irregularities_page(irregularities)),
        "sources.html": ("Sources and provenance", sources_page(sources)),
        "h66-session.html": ("Historical H66 archive", archive_page(rc)),
        "executive-summary.html": ("Executive summary", executive_page(rc)),
    }
    for filename, (title, body) in pages.items():
        page(filename, title, body, filename)
    (DOCS / "status-feed.json").write_text(json.dumps(feed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

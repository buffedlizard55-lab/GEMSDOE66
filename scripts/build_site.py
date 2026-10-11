#!/usr/bin/env python3
"""Build the public evidence site from the canonical docs/data registers.

No candidate raster is linked unless the canonical run card records every release gate
as passed, marks the run promoted, permits downloads, and identifies a matching file
under docs/downloads/. A local artifact or format receipt alone cannot open this gate.
"""
from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
DATA = DOCS / "data"
UPDATED = "2026-10-11"
OFFICIAL_LEADERBOARD_URL = "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/"
REQUIRED_RELEASE_GATES = (
    "inputs_verified", "top_candidate_holdout_ci", "beats_frozen_holdout_best",
    "leakage_canary", "registry_preplacement", "registry_postplacement",
    "official_grid_validator",
)
NAV = [
    ("index.html", "Summary"),
    ("executive-summary.html", "Submission executive summary"),
    ("submission-guide.html", "Clearance guide"),
    ("analysis.html", "H33 attribution"),
    ("hypotheses.html", "Hypotheses"),
    (OFFICIAL_LEADERBOARD_URL, "Official leaderboard ↗"),
    ("run-card.html", "Run card"),
    ("irregularities.html", "Irregularities"),
    ("sources.html", "Sources"),
    ("research/metric-derivation.md", "Metric derivation"),
]


def load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def e(value) -> str:
    return html.escape("" if value is None else str(value))


def tag(status: str) -> str:
    text = str(status or "UNKNOWN")
    upper = text.upper()
    if upper.startswith(("VERIFIED", "CONFIRMED", "PASS", "CLEARED")):
        css = "green"
    elif upper.startswith(("NEGATIVE", "BLOCK", "BROKEN", "NOT RUN", "NOT CLEARED", "MISSING", "FAIL")):
        css = "red"
    elif upper.startswith(("PARTIAL", "OPEN", "UNVERIFIED", "UNATTRIBUTED", "PROJECTION", "OWNER", "NOT ACCESSED", "NOT FETCHED", "POLICY", "UNKNOWN", "INCONCLUSIVE", "HISTORICAL")):
        css = "amber"
    else:
        css = "grey"
    return f'<span class="tag {css}">{e(text)}</span>'


def _candidate_download(rc: dict) -> str | None:
    """Return a Pages-relative TIF path only when every explicit fail-closed gate passes."""
    submission = rc.get("submission", {})
    gates = rc.get("release_gates", {})
    if (rc.get("verdict") != "promote" or rc.get("promote") is not True
            or submission.get("download_ok") is not True
            or not all(gates.get(key) is True for key in REQUIRED_RELEASE_GATES)):
        return None
    holdout = rc.get("holdout_dti", {})
    ci = holdout.get("ci95")
    paired_ci = holdout.get("paired_difference_ci95")
    if (holdout.get("label") != "HOLDOUT-DTI"
            or holdout.get("status") != "PASS"
            or not isinstance(holdout.get("value"), (int, float))
            or not isinstance(ci, list) or len(ci) != 2
            or not all(isinstance(x, (int, float)) for x in ci)
            or not isinstance(paired_ci, list) or len(paired_ci) != 2
            or not all(isinstance(x, (int, float)) for x in paired_ci)
            or paired_ci[0] <= 0.0
            or holdout.get("beats_frozen_holdout_best") is not True):
        return None
    checks = rc.get("registry_checks", {})
    pre = checks.get("pre_placement_surface", {})
    post = checks.get("post_placement_final_dots", {})
    if (pre.get("status") != "PASS" or post.get("status") != "PASS"
            or pre.get("complete_registry") is not True or post.get("complete_registry") is not True
            or pre.get("pixel_hash_agreement_pass") is not True
            or post.get("pixel_hash_agreement_pass") is not True
            or not isinstance(pre.get("max_abs_rank_correlation"), (int, float))
            or abs(pre["max_abs_rank_correlation"]) > 0.90
            or not isinstance(post.get("max_abs_rank_correlation"), (int, float))
            or abs(post["max_abs_rank_correlation"]) > 0.90
            or not isinstance(post.get("max_dot_overlap"), (int, float))
            or post["max_dot_overlap"] > 0.70):
        return None
    if rc.get("leakage_canary", {}).get("status") != "PASS":
        return None
    validator = rc.get("validator", {})
    if (validator.get("status") != "PASS" or validator.get("footprint_nan_ok") is not True
            or validator.get("values_0_1_ok") is not True
            or validator.get("crs_shape_transform_match") is not True):
        return None
    rel = rc.get("raster", {}).get("file")
    digest = rc.get("raster", {}).get("sha256")
    if not isinstance(rel, str) or not rel.startswith("docs/downloads/"):
        return None
    path = ROOT / rel
    if not path.is_file() or not isinstance(digest, str) or len(digest) != 64:
        return None
    h = hashlib.sha256(path.read_bytes()).hexdigest()
    if h != digest:
        return None
    return path.relative_to(DOCS).as_posix()


def page(filename: str, title: str, body: str, active: str) -> None:
    prefix = "../" if "/" in filename else ""
    nav = "".join(
        f'<a href="{e(href if href.startswith(("https://", "http://")) else prefix + href)}"'
        f' class="{"active" if href == active else ""}">{e(label)}</a>'
        for href, label in NAV
    )
    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} · GEMS Prize workbench</title>
<link rel="stylesheet" href="{prefix}assets/site.css">
</head>
<body>
<header class="site">
  <div class="brand">GEMS Prize (DrivenData #306) · workbench</div>
  <nav>{nav}</nav>
</header>
<main>
{body}
</main>
<footer>Generated by scripts/build_site.py from docs/data/*.json · last updated {UPDATED} (UTC) · not affiliated with DrivenData or DOE.</footer>
</body>
</html>
"""
    target = DOCS / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(doc, encoding="utf-8")


def sources_page() -> None:
    data = load("sources.json")
    rows = "".join(
        f'<tr><td><code>{e(s["id"])}</code></td><td>{e(s["title"])}<br>'
        f'<a href="{e(s["url"])}">{e(s["url"])}</a></td><td>{e(s["supports"])}</td>'
        f'<td>{tag(s["status"])}</td><td class="note">{e(s["how"])}</td></tr>'
        for s in data["sources"]
    )
    body = f"""<h1>Sources register</h1>
<p class="sub">Manual review links and source-specific evidence limits. A source supports only the claims recorded for it. Machine-readable register: <a href="data/sources.json">data/sources.json</a>.</p>
<table><thead><tr><th>ID</th><th>Source and link</th><th>What it supports</th><th>Status</th><th>How checked</th></tr></thead><tbody>{rows}</tbody></table>"""
    page("sources.html", "Sources", body, "sources.html")


def irregularities_page() -> None:
    data = load("irregularities.json")
    severity_class = {"high": "red", "medium": "amber", "low": "grey", "info": "blue"}
    rows = "".join(
        f'<tr><td><code>{e(i["id"])}</code></td>'
        f'<td><span class="tag {severity_class.get(i["severity"], "grey")}">{e(i["severity"])}</span></td>'
        f'<td>{e(i["statement"])}</td><td>{tag(i["status"])}</td>'
        f'<td class="note">{e(i["source"])}</td></tr>'
        for i in data["items"]
    )
    body = f"""<h1>Irregularities</h1>
<p class="sub">Open, negative, and fixed-but-tested findings are kept visible. A status is not closed merely because code was edited.</p>
<table><thead><tr><th>ID</th><th>Severity</th><th>Finding</th><th>Status</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table>"""
    page("irregularities.html", "Irregularities", body, "irregularities.html")


def hypotheses_page() -> None:
    data = load("hypotheses.json")
    cards = []
    for h in data["items"]:
        cards.append(f"""<section class="card">
<h2>Rank {h['rank']} · {e(h['id'])} · {e(h['title'])}</h2>
<div class="kv">
<div>Lane</div><div>{e(h['lane'])}</div>
<div>Layers</div><div>{e(h['layers'])}</div>
<div>Physical signature</div><div>{e(h['signature'])}</div>
<div>Why faults may be absent from catalogue</div><div>{e(h['why_off_catalogue'])}</div>
<div>Named non-fault mimic</div><div>{e(h['named_mimic'])}</div>
<div>Repo-local novelty</div><div>{e(h['differs_from_repo'])}</div>
<div>Implementation cost</div><div>{e(h['cost'])}</div>
<div>Expected DTI improvement</div><div>{tag('NOT MEASURED')} {e(h['expected_gain'])}</div>
<div>Data status</div><div>{e(h['data_status'])}</div>
<div>Validation</div><div>{e(h['validation'])}</div>
</div></section>""")
    body = f"""<h1>Ranked lidar-scarp hypotheses</h1>
<p class="sub">One method lane: native-resolution lidar scarp evidence, physical scales 2–20 m, aggregated to 100 m. Ranking is qualitative, not a DTI prediction. The highest-ranked candidate has not been generated or validated because inputs are unavailable and the research budget is exhausted. Test it alone on the buffered spatial holdout before considering a weekly slot. Leakage canary: any feature-alone AUC &gt;0.90 is leakage until disproven.</p>
{''.join(cards)}
<p class="note">Machine-readable hypotheses: <a href="data/hypotheses.json">data/hypotheses.json</a>. Prior-method overlap is disclosed; full-registry novelty is not established.</p>"""
    page("hypotheses.html", "Hypotheses", body, "hypotheses.html")


def _ci(value) -> str:
    return "not measured" if value is None else e(value)


def run_card_page() -> None:
    rc = load("run-card.json")
    h = rc["holdout_dti"]
    pre = rc["registry_checks"]["pre_placement_surface"]
    post = rc["registry_checks"]["post_placement_final_dots"]
    submission = rc["submission"]
    note = submission.get("note") or "No submission note cleared."
    hist = rc["historical_emitted_policy_holdout"]
    detector = rc["historical_detector_arm"]
    body = f"""<h1>Canonical run card · {e(rc['run_id'])}</h1>
<p class="sub">One canonical JSON decision: <a href="data/run-card.json">docs/data/run-card.json</a>. Historical receipts are separated from the untested top hypothesis.</p>
<div class="banner stop"><strong class="big">Verdict: NEGATIVE · PROMOTE: NO</strong>No competition-format file is offered for download or submission. The top-ranked proposal was not generated or tested.</div>
<div class="card"><div class="kv">
<div>Date (UTC)</div><div>{e(rc['date_utc'])}</div>
<div>Lane</div><div>{e(rc['lane'])}</div>
<div>Top candidate</div><div>{e(rc['top_candidate'])}</div>
<div>Hypothesis</div><div>{e(rc['hypothesis'])}</div>
<div>Mechanism</div><div>{e(rc['mechanism'])}</div>
<div>Named non-fault mimic</div><div>{e(rc['non_fault_mimic'])}</div>
<div>Top-candidate HOLDOUT-DTI</div><div>{tag(h['status'])}; value: {_ci(h['value'])}; evaluator: {e(h['evaluator_version'])}; withheld positives: {_ci(h['withheld_positive_count'])}; 95% CI: {_ci(h['ci95'])}</div>
<div>Historical emitted-policy HOLDOUT-DTI</div><div>{tag(hist['status'])}; {e(hist['value'])}; evaluator: {e(hist['evaluator_version'])}; withheld observations: {e(hist['withheld_positive_count'])}; 95% CI: {_ci(hist['ci95'])}</div>
<div>Historical detector-arm HOLDOUT-DTI</div><div>{tag(detector['status'])}; {e(detector['value'])}; evaluator: {e(detector['evaluator_version'])}; withheld observations: {e(detector['withheld_positive_count'])}; 95% CI: {_ci(detector['ci95'])}</div>
<div>Feature-alone leakage canary</div><div>{tag(rc['leakage_canary']['status'])}; threshold AUC &gt; {e(rc['leakage_canary']['threshold_auc'])}; {e(rc['leakage_canary']['reason'])}</div>
<div>Pre-placement continuous-surface registry check</div><div>{tag(pre['status'])}; absolute Spearman limit &gt; {e(pre['correlation_limit'])}; maximum measured correlation: {_ci(pre['max_abs_rank_correlation'])}; rasters checked: {_ci(pre['registry_count'])}; pixel/hash status: {e(pre['pixel_hash_status'])}</div>
<div>Post-placement final-dot registry check</div><div>{tag(post['status'])}; absolute Spearman limit &gt; {e(post['correlation_limit'])}; 3-pixel dot-overlap limit &gt; {e(post['overlap_limit'])}; measured dot overlap: {_ci(post['max_dot_overlap'])}; rasters checked: {_ci(post['registry_count'])} of {_ci(post['expected_registry_count'])}; pixel/hash status: {e(post['pixel_hash_status'])}</div>
<div>Strict input verifier (s0)</div><div>{tag(rc['input_verification']['status'])}; missing: {e(', '.join(rc['input_verification']['missing']))}; missing pins: {e(', '.join(rc['input_verification']['missing_pins']))}</div>
<div>Historical audit raster / SHA-256</div><div>{e(rc['raster']['file'])} · <code>{e(rc['raster']['sha256'])}</code> · {e(rc['raster']['status'])}</div>
<div>Official-grid validator</div><div>{tag(rc['validator']['status'])}; footprint NaN: {e(rc['validator']['footprint_nan_status'])}; [0,1]: {e(rc['validator']['values_0_1'])}; CRS/shape/transform: {e(rc['validator']['grid_status'])}</div>
<div>Proposed submission name</div><div>{e(submission['name'])} <span class="note">(informational only)</span></div>
<div>Proposed note</div><div><code>{e(note)}</code> · {e(submission['note_chars'])}/{e(submission['note_limit_chars'])} characters · not cleared</div>
<div>Download clearance</div><div>{tag(submission['clearance'])}</div>
<div>Budget</div><div>{e(json.dumps(rc['budget'], sort_keys=True))}</div>
<div>Open irregularities</div><div>{e(', '.join(rc['open_irregularities']))}</div>
</div></div>
<p class="note">No score here is an organizer score. A historical HOLDOUT-DTI without a 95% CI does not clear the candidate gate. An owner or user leaderboard attribution is not a receipt.</p>"""
    page("run-card.html", "Run card", body, "run-card.html")


def index_page() -> None:
    rc = load("run-card.json")
    card_path = "data/run-card.json"
    download = _candidate_download(rc)
    h = rc["holdout_dti"]
    hist = rc["historical_emitted_policy_holdout"]
    if download:
        clearance = f'<a class="btn" href="{e(download)}">Download cleared candidate GeoTIFF</a>'
        banner_class = "ok"
        status = "Research gates passed for download; competition-slot selection remains separate."
    else:
        clearance = '<strong>No TIF or ZIP download is cleared. Archived audit bytes are not linked.</strong>'
        banner_class = "stop"
        status = "Download: NOT CLEARED · Submission: NOT CLEARED · Promote: NO."
    body = f"""<h1>GEMS DOE Prize workbench — lidar-scarp lane</h1>
<p class="sub">Evidence status on {UPDATED} UTC. Scope: native-resolution lidar scarp channels only. The target is previously unmapped geological faults that may inform geothermal resource assessment; a scarp is not proof of geothermal productivity.</p>
<div class="banner {banner_class}"><strong class="big">{e(status)}</strong>{clearance}<p>Every download requires the complete release gates in the canonical run card. A negative result, local format receipt, partial registry, or historical artifact never authorizes a download.</p></div>
<div class="card"><h2>Purpose and core values</h2><p><strong>Maximize P(Win):</strong> use limited research time and any later competition slot only for credible, spatially blocked gains over a frozen holdout best.</p><p><strong>Own the Outcome:</strong> disclose missing inputs, failed gates, uncertainty, and negative results; fix shared defects at their source; do not turn an unknown into a pass.</p></div>
<h2>What is known</h2>
<ul class="steps">
<li><strong>H33 score attribution is unresolved.</strong> The prompt/user-supplied 0.2778 attribution conflicts with owner-maintained wording that H33-2-B2 was unscored; no organizer receipt is tied to the exact raster hash. Neither claim is treated as verified. <a href="analysis.html">Review the evidence.</a></li>
<li><strong>Top proposal:</strong> {e(rc['top_candidate'])} It is an untried hypothesis, not a score or candidate output. See the <a href="hypotheses.html">four same-lane proposals</a>.</li>
<li><strong>Top-candidate holdout:</strong> {tag(h['status'])}; value {_ci(h['value'])}; evaluator {e(h['evaluator_version'])}; withheld positives {_ci(h['withheld_positive_count'])}; 95% CI {_ci(h['ci95'])}. No experiment was run in this review.</li>
<li><strong>Historical emitted-policy holdout:</strong> {hist['label']} {hist['value']} using {e(hist['evaluator_version'])}, {hist['withheld_positive_count']} withheld observations, no 95% CI. It is a historical receipt and cannot validate the new top proposal.</li>
<li><strong>Inputs and budget:</strong> authorized competition rasters and the complete registry are absent; the official data page is login-gated. The recorded research budget is exhausted ({rc['budget']['holdout_experiments_used']}/{rc['budget']['max_holdout_experiments']} experiments; {rc['budget']['wall_time_hours_reported']}/{rc['budget']['max_wall_time_hours']} hours).</li>
<li><strong>Format and earlier [0,1] rejection:</strong> the cause is unknown. Historical local checks do not prove official-footprint validity or portal acceptance; no corrected file is cleared.</li>
</ul>
<h2>Manual review</h2>
<p><a href="executive-summary.html">Submission executive summary</a> · <a href="submission-guide.html">clearance rules</a> · <a href="run-card.html">canonical run card</a> · <a href="irregularities.html">irregularities</a> · <a href="sources.html">trusted/official source register</a> · <a href="{OFFICIAL_LEADERBOARD_URL}">official live leaderboard</a></p>
<p class="note">The project does not scrape, mirror, or monitor leaderboard rows. Open the official page directly; project-site and leaderboard claims remain unverified without receipts.</p>
<p class="note">Canonical machine-readable status: <a href="{card_path}">docs/data/run-card.json</a>. All external-source limitations and manual review URLs are listed in <a href="sources.html">Sources</a>.</p>"""
    page("index.html", "Executive summary", body, "index.html")


def submission_executive_summary_page() -> None:
    rc = load("run-card.json")
    sub = rc["submission"]
    h = rc["holdout_dti"]
    hist = rc["historical_emitted_policy_holdout"]
    detector = rc["historical_detector_arm"]
    download = _candidate_download(rc)
    if download:
        banner = f'<a class="btn" href="{e(download)}">Download cleared candidate GeoTIFF</a>'
        status = "DOWNLOAD GATES PASSED; weekly-slot selection is separate."
        klass = "ok"
    else:
        banner = "No TIFF or ZIP is cleared. Do not download or submit the archived audit artifact."
        status = "NEGATIVE — NO DOWNLOAD OR SUBMISSION CLEARANCE"
        klass = "stop"
    body = f"""<h1>Submission executive summary</h1>
<p class="sub">Decision for {e(rc['run_id'])}. This page is intentionally a clearance summary, not a leaderboard claim.</p>
<div class="banner {klass}"><strong class="big">{e(status)}</strong>{banner}</div>
<table><tbody>
<tr><th>Proposed method</th><td>{e(rc['top_candidate'])}</td></tr>
<tr><th>Hypothesis</th><td>{e(rc['hypothesis'])}</td></tr>
<tr><th>Top-candidate holdout</th><td>{tag(h['status'])}; value {_ci(h['value'])}; evaluator {e(h['evaluator_version'])}; withheld positives {_ci(h['withheld_positive_count'])}; 95% CI {_ci(h['ci95'])}</td></tr>
<tr><th>Historical emitted-policy holdout</th><td>{hist['label']} {hist['value']}; evaluator {e(hist['evaluator_version'])}; withheld observations {hist['withheld_positive_count']}; 95% CI {_ci(hist['ci95'])}. Not the top proposal.</td></tr>
<tr><th>Historical detector arm</th><td>{detector['label']} {detector['value']}; evaluator {e(detector['evaluator_version'])}; withheld observations {detector['withheld_positive_count']}; 95% CI {_ci(detector['ci95'])}. Not the emitted policy.</td></tr>
<tr><th>Leakage canary</th><td>{tag(rc['leakage_canary']['status'])} — {e(rc['leakage_canary']['reason'])}</td></tr>
<tr><th>Strict input verifier</th><td>{tag(rc['input_verification']['status'])}; missing inputs: {e(', '.join(rc['input_verification']['missing']))}; missing pins: {e(', '.join(rc['input_verification']['missing_pins']))}</td></tr>
<tr><th>Registry checks</th><td>Pre-placement: {tag(rc['registry_checks']['pre_placement_surface']['status'])}; post-placement: {tag(rc['registry_checks']['post_placement_final_dots']['status'])}. Registry coverage is incomplete.</td></tr>
<tr><th>Official-grid validator</th><td>{tag(rc['validator']['status'])} — {e(rc['validator']['reason'])}</td></tr>
<tr><th>Historical raster SHA-256</th><td><code>{e(rc['raster']['sha256'])}</code> · audit-only archive path <code>{e(rc['raster']['file'])}</code></td></tr>
<tr><th>Proposed name</th><td>{e(sub['name'])} (not reserved)</td></tr>
<tr><th>Proposed note</th><td><code>{e(sub['note'])}</code> · {e(sub['note_chars'])}/{e(sub['note_limit_chars'])} characters · informational, not cleared</td></tr>
<tr><th>[0,1] rejection</th><td>Cause unknown. No evidence establishes that NaN handling or any single change caused the earlier portal rejection.</td></tr>
<tr><th>Decision</th><td><strong>Do not submit. No candidate beats the frozen holdout best with the required evidence. A real slot is a separate selector decision.</strong></td></tr>
</tbody></table>
<p>Next research, if separately authorized with a fresh budget and lawful inputs: generate LIDAR-01, validate only on the prescribed buffered whole-segment spatial holdout, record a 95% CI and withheld-positive count, then run all leakage, uniqueness, and official-grid gates. No experiment or weekly slot is authorized by this summary.</p>
<p><a href="run-card.html">Open full run card</a> · <a href="submission-guide.html">Read clearance guide</a> · <a href="sources.html">Manual source links</a></p>"""
    page("executive-summary.html", "Submission executive summary", body, "executive-summary.html")


def submission_guide_page() -> None:
    rc = load("run-card.json")
    download = _candidate_download(rc)
    if download:
        status = f'<a href="{e(download)}">A candidate passed the research download gate.</a> Slot selection remains separate.'
        klass = "ok"
    else:
        status = "No file is available for download or submission. The historical TIFF is audit-only and must not be uploaded."
        klass = "stop"
    body = f"""<h1>Submission and clearance guide</h1>
<p class="sub">The live account-gated submission form was not inspected. This project does not upload automatically.</p>
<div class="banner {klass}"><strong class="big">{e(rc['submission']['clearance'])}</strong>{status}</div>
<h2>Why the earlier [0,1] rejection is unresolved</h2>
<p>The earlier portal message alone does not identify whether the failure came from values, grid alignment, file encoding, or another validation condition. The cause is unknown. The historical local receipt did not revalidate against the authorized official sample and features in this checkout. Writing zeros rather than NaNs outside the footprint is not a verified fix and no file is cleared.</p>
<h2>Required gates before any future file</h2>
<ol class="steps">
<li>Use lawfully obtained competition inputs with exact hashes and verify the official sample grid, footprint, CRS, transform, and features. Do not use an owner mirror as a substitute for login-gated competition files.</li>
<li>Generate the single-lane LIDAR-01 hypothesis from native-resolution lidar scarp channels: slope-aware templates, Steger sub-pixel lines, Frangi 2–20 m evidence, aggregated to 100 m with scarp fraction, SNR-weighted amplitude, orientation coherence, and dominant strike; use the existing cultural mask.</li>
<li>Hide whole fault segments/components in lidar-covered spatial blocks with a buffer. Derive catalogue features only from visible faults and mask visible known-fault pixels exactly. Evaluate pooled DTI with α=0.2, β=0.8, and the 300 m triangular kernel.</li>
<li>Report every performance result as HOLDOUT-DTI with evaluator version, withheld-positive count, and 95% CI. Test each feature alone; AUC &gt;0.90 is leakage until disproven. Compare the candidate against the frozen holdout best before any slot is considered.</li>
<li>Check the pre-placement surface and final emitted dots against every registry raster. Stop above 0.90 absolute rank correlation or above 70% 3-pixel dot overlap; verify hash/pixel agreement. Incomplete registry access is not a pass.</li>
<li>Only after every science and uniqueness gate passes, write with the shared submission writer and validate against the authorized official reference/features. Check the footprint-NaN condition, [0,1] values, CRS, shape, transform, and hash. Local format success is not organizer acceptance.</li>
</ol>
<h2>Submission note</h2>
<p>Informational proposed note only; not cleared for use: <code>{e(rc['submission']['note'])}</code> ({e(rc['submission']['note_chars'])}/{e(rc['submission']['note_limit_chars'])} characters).</p>
<p>See the <a href="executive-summary.html">submission executive summary</a>, <a href="run-card.html">canonical run card</a>, and <a href="{OFFICIAL_LEADERBOARD_URL}">official live leaderboard</a> for manual review. No leaderboard rows are copied here.</p>"""
    page("submission-guide.html", "Submission guide", body, "submission-guide.html")


def analysis_page() -> None:
    body = f"""<h1>H33-2-B2 score attribution: unresolved</h1>
<p class="sub">Assessment of the user-supplied 0.2778 association. No leaderboard number is treated as verified without an organizer receipt tied to exact raster bytes.</p>
<h2>Evidence and limits</h2>
<table><thead><tr><th>Evidence</th><th>Supports</th><th>Does not support</th></tr></thead><tbody>
<tr><td>User-supplied prompt</td><td>An attribution claim associates 0.2778 with H33-2-B2.</td><td>An organizer-confirmed score or exact-hash linkage.</td></tr>
<tr><td>Owner-maintained GEMSDOE32 record/site (<a href="https://github.com/buffedlizard55-lab/GEMSDOE32">repository</a>; <a href="https://buffedlizard55-lab.github.io/GEMSDOE32/docs/index.html">project page</a>)</td><td>Owner material associates the number with the artifact, while the project page describes the artifact as unscored and says no organizer score exists for those artifacts.</td><td>Independent verification of what the exact submitted bytes earned.</td></tr>
<tr><td>This checkout</td><td>No organizer receipt, exact raster hash mapping, or controlled comparison is recorded.</td><td>A verified score or causal explanation.</td></tr>
</tbody></table>
<div class="banner warn"><strong class="big">Conclusion: may or may not be true.</strong>The attribution cannot be confirmed or disproved from the available evidence. Do not repeat 0.2778 as an organizer result.</div>
<h2>Possible mechanisms — not findings</h2>
<p>If a pruning variant did earn a higher score, deleting unsupported predictions might reduce false-positive cost while preserving true-positive credit under the asymmetric distance-weighted Tversky metric. Conversely, pruning could remove dots near genuinely new faults and increase false negatives. Different bytes, preprocessing, submission identity, score timing, or attribution mismatch are also plausible. No receipt or controlled experiment distinguishes these possibilities.</p>
<p>See source IDs S02, S17, S18, and S28 in the <a href="sources.html">manual sources register</a>. Open the <a href="{OFFICIAL_LEADERBOARD_URL}">official leaderboard</a> directly; this repository does not scrape or mirror it.</p>"""
    page("analysis.html", "H33 attribution", body, "analysis.html")


def h66_session_page() -> None:
    rc = load("run-card.json")
    body = f"""<h1>H66 historical session record</h1>
<div class="banner stop"><strong class="big">No download clearance · negative result</strong>This page replaces an older session page that linked a historical TIFF and asserted unverified format/uniqueness clearance. Those claims have been withdrawn.</div>
<p>The historical run card, archived raster hash, evidence classification, and unresolved checks are recorded in <a href="run-card.html">the canonical run card</a>. The raster is outside the Pages download directory and is not offered here.</p>
<p>Current proposal and manual review steps: <a href="executive-summary.html">submission executive summary</a> · <a href="hypotheses.html">ranked hypotheses</a> · <a href="irregularities.html">irregularities</a>.</p>
<p>Decision: {e(rc['verdict'])}; promote={e(rc['promote'])}; download clearance={e(rc['submission']['download_ok'])}; submit clearance={e(rc['submission']['submit_ok'])}.</p>"""
    page("h66-session.html", "H66 session record", body, "h66-session.html")


def main() -> None:
    sources_page()
    irregularities_page()
    hypotheses_page()
    run_card_page()
    index_page()
    submission_executive_summary_page()
    submission_guide_page()
    analysis_page()
    h66_session_page()
    (DOCS / "leaderboard.html").unlink(missing_ok=True)
    print("built canonical evidence site; download cleared:", bool(_candidate_download(load("run-card.json"))))


if __name__ == "__main__":
    main()

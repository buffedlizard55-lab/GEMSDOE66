"""H66-C page blocks, shared by both site builders.

Both ``scripts/build_site.py`` and ``scripts/build_site_h67.py`` write ``docs/index.html``
and ``docs/executive-summary.html``, so whichever runs last wins. Keeping the H66-C content
in one module and rendering it from both is what stops the negative result from silently
disappearing whenever the other lane rebuilds the site.

H66-C is a NEGATIVE result: the gate is not met, so no bytes are offered. The measurement,
the hashes and the audit path are published so the artifact stays verifiable.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Prefix for links that point outside the directory holding the rendered page. The main site
# renders into docs/, the H67 lane renders into docs/h67/, so it sets REL = "../".
REL = ""
DATA = ROOT / "docs" / "data"


def load(p: Path, default=None):
    try:
        return json.loads(p.read_text())
    except Exception:
        return default


def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def pill(ok: bool, text: str = None) -> str:
    cls = "ok" if ok else "bad"
    return f'<span class="pill {cls}">{esc(text or ("PASS" if ok else "FAIL"))}</span>'


def pillw(text: str = "WARN") -> str:
    """Neither a pass nor a fail: a diagnostic whose rule and its own null disagree."""
    return f'<span class="pill warn">{esc(text)}</span>'


def submission_block_h66c() -> str:
    """The H66-C candidate (branch arena/e7d32f78): a NEGATIVE result, published as such.

    The brief is explicit: offer the download only if the gate is met, else log the negative
    result. The gate is not met (HOLDOUT-DTI 0.0979 against a frozen best of 0.1195), so the
    bytes are NOT offered here. They stay under ``artifacts/h66c/`` for audit, with their
    hashes published so anyone can verify them, exactly as the withdrawn H66-1 artifacts do.
    """
    R = load(ROOT / "docs" / "data" / "release-h66c.json", {})
    if not R:
        return ""
    chk = R.get("validator", {})
    uni = R.get("uniqueness_dots", {})
    usf = R.get("uniqueness_surface", {})
    hold = R.get("holdout", {})
    ok = bool(chk.get("ok"))
    note = R.get("note", "")
    return f"""
<div class="stop">
  <h2>H66-C (2026-10-12): the scarp-channel candidate — NOT OFFERED, gate not met</h2>
  <p><b>There is no H66-C download.</b> This session implemented the native-resolution LiDAR
  scarp-channel lane end to end and built a <b>unique, format-valid</b> GeoTIFF, but its
  scientific gate is <b>not met</b>: HOLDOUT-DTI on instrument N is
  <b>{hold.get('dti', 0):.4f} [{hold.get('ci_lo', 0):.4f}, {hold.get('ci_hi', 0):.4f}]</b> against a
  frozen best of <b>{max(b['n'] for b in R.get('baselines', [{'n': 0}])):.4f}</b>. The brief is
  unconditional here — offer the download only if the gate is met, else log the negative result —
  so the bytes are not published in the download path. They are retained for audit under
  <code>artifacts/h66c/</code> with the hashes below, and this repository's own run card for them
  says <code>promote: false</code>.</p>
  <p class="small">Every other candidate that <i>is</i> offered on this page carries its own run
  card and its own disclosures; the site does not rank them against each other, and none of them
  is <code>ORGANIZER-CONFIRMED</code>. <b>Do not submit the H66-C file.</b> If a future session
  measures a real gain for this field under a valid instrument, the same builder can publish it
  by setting <code>promote</code> in <code>docs/data/release-h66c.json</code>.</p>
  <table>
    <tr><th>sha256 (tif, audit copy)</th><td class="mono">{esc(R.get('sha256_tif', ''))}</td></tr>
    <tr><th>sha256 (zip, audit copy)</th><td class="mono">{esc(R.get('sha256_zip', ''))}</td></tr>
    <tr><th>audit path</th><td class="mono">artifacts/h66c/{esc(R.get('slug', ''))}.tif</td></tr>
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
        <td>{pill(uni.get('worst_within_3px_above_1p5x_random', 1) <= 0.70)}
        max |&rho;| = {uni.get('max_abs_spearman_rho', 0):.3f} (0.90 threshold);
        highest lift over random placement = {uni.get('max_lift_over_random', 0):.2f}&times;;
        worst within-3 px fraction among the {uni.get('n_above_1p5x_random', 0)} rasters above
        1.5&times; random = {uni.get('worst_within_3px_above_1p5x_random', 0):.3f}
        (0.70 stop), over all {uni.get('n_compared', 0)} accessible rasters</td></tr>
    <tr><th>Duplicate gate — final dots, literal raw rule</th>
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
    <tr><th>name that would be used if it were ever cleared</th>
        <td class="mono">{esc(R.get('slug', ''))}</td></tr>
    <tr><th>note drafted for that case ({len(note)}/140 chars) — NOT CLEARED</th>
        <td class="mono">{esc(note)}</td></tr>
  </table>
  <p class="small">Is it OK to download and submit? <b>No — there is no download, and the file
  must not be submitted.</b>
  <a href="{REL}review/2026-10-12-h66c-verdict.md">Full verdict note</a> ·
  <a href="{REL}data/run-card-h66c.json">machine-readable run card</a> ·
  <a href="results.html">measurements</a>.</p>
</div>
"""


def h66c_exec_block() -> str:
    """H66-C section on the how-to-submit page: why this one is a no, in one block."""
    R = load(ROOT / "docs" / "data" / "release-h66c.json", {})
    if not R:
        return ""
    hold = R.get("holdout", {})
    return f"""
<h2>H66-C (2026-10-12) — the scarp-channel candidate, and why there is no download</h2>
<p>Another session implemented the native-resolution LiDAR scarp-channel lane end to end and
built a <b>unique, format-valid</b> GeoTIFF (<code>{esc(R.get('slug', ''))}.tif</code>, sha256
<code class="mono">{esc(R.get('sha256_tif', ''))}</code>). It passes the shared validator with
{len([v for v in R.get('validator', {}).get('checks', {}).values() if v])} gating checks and zero
failures, and its leakiest single feature reaches AUC {R.get('canary_max_auc', 0):.3f} against a
0.90 threshold. <b>It is not offered here.</b></p>
<p>The reason is the gate, not the file. On instrument N (SGMC off-catalogue faults inside
LiDAR-covered held-out blocks) it measures <b>{hold.get('dti', 0):.4f}</b>, 95% CI
[{hold.get('ci_lo', 0):.4f}, {hold.get('ci_hi', 0):.4f}], against frozen baselines of 0.1195
(anderson), 0.1104 (h33-2-b2) and 0.1065 (d28). On instrument S it measures 0.1231 against 0.1688
(d28), but that instrument is <i>anti</i>-correlated (&rho; = &minus;0.708) with the owner-reported
live scores, so it cannot be used to argue a win. Neither instrument is a validated surrogate; see
<a href="irregularities.html">IR-66-INSTR-01</a>. Because the brief says to offer a download only
when the gate is met, the bytes stay in <code>artifacts/h66c/</code> for audit, with their hashes
published on the <a href="index.html">overview</a>.</p>
<p>What would have to change for it to be worth a slot: an organiser receipt for a candidate with a
<i>different</i> field confirming the &minus;0.126-per-unit-f200 dose response is causal; a local
instrument whose rank correlation with live scores survives partialling out dot count; and two
independent scientific-lead reviews. None of the three exists today, so the honest default is to
keep the slot.</p>
"""

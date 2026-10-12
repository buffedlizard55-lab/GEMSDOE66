#!/usr/bin/env python3
"""Build the GitHub Pages site for GEMSDOE66, including the download decision.

The download verdict is recomputed HERE, at build time, by re-reading the artifact from disk
and re-running the official-format validator and the registry uniqueness audit.  A stale page
therefore cannot advertise a file that no longer passes.  The verdict is a single boolean made
from named gates; every gate's evidence is printed into the page.

Usage:  python3 scripts/build_site_h67.py
"""
from __future__ import annotations

import glob
import hashlib
import html
import json
import shutil

import h66c_blocks
from h66c_blocks import submission_block_h66c, h66c_exec_block, pillw  # noqa: E402  (other lane's blocks, kept visible)
import sys
import time
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

DOCS = ROOT / "docs"
SITE = DOCS / "h67"        # this lane's pages; docs/*.html belong to build_site.py
DL = DOCS / "downloads"
ART = ROOT / "artifacts" / "h67"
EVID = ROOT / "evidence"

OFFICIAL = "https://www.drivendata.org/"
PROBLEM = "https://www.drivendata.org/competitions/306/competition-doe-gems/page/967/"
ABOUT = "https://www.drivendata.org/competitions/306/competition-doe-gems/page/968/"
RULES = "https://www.drivendata.org/competitions/306/competition-doe-gems/rules/"
LEADERBOARD = "https://www.drivendata.org/competitions/306/competition-doe-gems/leaderboard/"
REFSOL = "https://github.com/drivendataorg/gems-prize-reference-solution"
GEODAWN = "https://www.usgs.gov/data/geodawn-airborne-magnetic-and-radiometric-surveys-northwestern-great-basin-nevada-and"
SGMC = "https://mrdata.usgs.gov/geology/state/"
GDR = "https://gdr.openei.org/submissions/1391"
EPSG = "https://epsg.io/32611"
TVERSKY = "https://en.wikipedia.org/wiki/Tversky_index"

NAV = [("index.html", "Download & status"), ("executive-summary.html", "How to submit"),
       ("results.html", "Results"), ("hypotheses.html", "Hypotheses"),
       ("method.html", "Method & metric"), ("sources.html", "Sources"),
       ("irregularities.html", "Irregularities"), ("run-card.html", "Run card")]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def newest(pattern: str) -> Path | None:
    hits = sorted(glob.glob(pattern), key=lambda p: Path(p).stat().st_mtime)
    return Path(hits[-1]) if hits else None


def page(title: str, active: str, body: str) -> str:
    links = []
    for h, t in NAV:
        cls = ' class="on"' if h == active else ""
        links.append(f'<a href="{h}"{cls}>{html.escape(t)}</a>')
    nav = "".join(links)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · GEMSDOE66</title>
<link rel="stylesheet" href="assets/site.css"></head>
<body><header class="top"><div class="wrap">
<h1 class="logo">GEMSDOE66 &mdash; DOE GEMS Prize fault discovery</h1>
<nav class="main">{nav}</nav></div></header>
<main><div class="wrap">
{body}
</div></main>
<footer class="wrap"><p class="small">Built {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
by <code>scripts/build_site_h67.py</code>. Every number on this site is either HOLDOUT-DTI
(internal, with its evaluator and CI) or a measurement of our own bytes. Nothing here is an
organizer score.</p></footer>
</body></html>
"""


def css() -> str:
    return """
:root{--ink:#12181f;--mut:#5b6875;--line:#dfe5ec;--bg:#f6f8fa;--ok:#0b7a3b;--bad:#b3261e;--acc:#0b5cab}
*{box-sizing:border-box}
body{margin:0;font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:#fff}
.wrap{max-width:1040px;margin:0 auto;padding:0 20px}
header.top{border-bottom:1px solid var(--line);background:var(--bg)}
h1.logo{font-size:19px;margin:14px 0 6px}
nav.main{display:flex;flex-wrap:wrap;gap:4px;margin:0 0 10px}
nav.main a{color:var(--mut);text-decoration:none;padding:6px 10px;border-radius:6px;font-size:14px}
nav.main a:hover{background:#eaeff5}
nav.main a.on{background:var(--acc);color:#fff}
main{padding:26px 0 60px}
h2{font-size:22px;margin:30px 0 10px;border-bottom:1px solid var(--line);padding-bottom:6px}
h3{font-size:17px;margin:22px 0 6px}
p{margin:10px 0}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px}
th,td{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}
th{background:var(--bg);font-weight:600;white-space:nowrap}
code,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:12.5px;word-break:break-all}
.small{font-size:13px;color:var(--mut)}
.pill{display:inline-block;padding:2px 8px;border-radius:999px;font-size:12px;font-weight:700;letter-spacing:.02em}
.pill.ok{background:#e2f5e9;color:var(--ok)}
.pill.bad{background:#fde8e7;color:var(--bad)}
.pill.warn{background:#fff4d6;color:#8a6100}
.banner{border:2px solid;border-radius:10px;padding:18px 20px;margin:18px 0}
.banner.go{border-color:var(--ok);background:#f2fbf5}
.banner.stop{border-color:var(--bad);background:#fdf3f2}
.banner h2{border:0;margin:0 0 8px;font-size:24px}
.dl{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0}
.dl a{display:inline-block;background:var(--ok);color:#fff;text-decoration:none;font-weight:700;
      padding:14px 22px;border-radius:8px;font-size:17px}
.dl a.alt{background:var(--acc)}
.note{background:#f2f7fd;border-left:4px solid var(--acc);padding:10px 14px;margin:14px 0;border-radius:0 6px 6px 0}
.stop-box{background:#fdf3f2;border-left:4px solid var(--bad);padding:10px 14px;margin:14px 0;border-radius:0 6px 6px 0}
ol li,ul li{margin:6px 0}
footer{border-top:1px solid var(--line);padding:16px 0 40px;color:var(--mut)}
.kv{font-size:14px}
"""


def assess(card_path: Path | None) -> dict:
    """Recompute the release verdict from the artifact on disk.  Nothing is trusted from the card."""
    from gems import validate_submission
    from gems67 import stack as h67stack

    ref = h67stack.RAW / "sample_submission.tif"
    feats = h67stack.RAW / "training_features.tif"
    out: dict = {"card": None, "gates": {}, "cleared": False, "reasons": []}
    if card_path is None or not card_path.exists():
        out["reasons"].append("no H67 run card found under artifacts/h67/")
        return out
    card = json.loads(card_path.read_text())
    out["card"] = card
    tif = ART / card["raster"]["file"]
    zips = list(ART.glob(card["submission"]["name"] + ".zip"))
    if not tif.exists():
        out["reasons"].append(f"raster {tif.name} is not on disk")
        return out
    if not zips:
        out["reasons"].append("zip companion is not on disk")
        return out
    zip_path = zips[0]

    report = validate_submission.validate(tif, ref, feats)
    with rasterio.open(tif) as ds:
        arr = ds.read(1).astype(np.float64)
        crs, transform, shape = ds.crs, tuple(ds.transform)[:6], (ds.height, ds.width)
        dtype, count = ds.dtypes[0], ds.count
    with rasterio.open(ref) as ds:
        ref_crs, ref_transform, ref_shape = ds.crs, tuple(ds.transform)[:6], (ds.height, ds.width)
    with rasterio.open(feats) as ds:
        _b = ds.read(1).astype(np.float64)
        feat_fp = np.isfinite(_b) & (_b > -1e38)
    # IR-67-FOOTPRINT-01: the organiser's sample submission is the authoritative mask -- all 12
    # scored owner artifacts are finite on exactly its 5,167,373 cells.  The features band-1 mask
    # differs by 3,061 / 1,540 cells and is reported as a cross-check, not as the criterion.
    with rasterio.open(ref) as ds:
        fp = np.isfinite(ds.read(1).astype(np.float64))
    fp_disagree = (int((fp & ~feat_fp).sum()), int((feat_fp & ~fp).sum()))
    finite = np.isfinite(arr)
    vals = arr[finite]

    uniq_path = ART / f"uniqueness-{card['submission']['name']}.json"
    uniq = json.loads(uniq_path.read_text()) if uniq_path.exists() else {"comparisons": []}
    max_rho = max((abs(c["spearman_rho_surface"]) for c in uniq["comparisons"]), default=0.0)
    max_lift = max((c["lift_over_random"] or 0.0 for c in uniq["comparisons"]), default=0.0)
    max_within3 = max((c["frac_cand_dots_within_3px"] for c in uniq["comparisons"]), default=0.0)
    sha_twins = sum(1 for c in uniq["comparisons"] if c.get("sha256_identical_to_candidate"))
    max_coincident = max((c["coincident_dots"] for c in uniq["comparisons"]), default=0)
    # IR-66-GATE-01: raw overlap must be judged against that raster's OWN random null, and the
    # two numbers must come from the SAME raster -- maxing them independently mixes rasters.
    def _nb(c):
        return c.get("lift_over_neighbourhood_null")
    dup_rasters = [c["raster"] for c in uniq["comparisons"]
                   if c["frac_cand_dots_within_3px"] > 0.70
                   and (_nb(c) is None or _nb(c) >= 3.0)]
    worst = max(uniq["comparisons"], key=lambda c: c["frac_cand_dots_within_3px"], default=None)
    null_of_worst = worst["frac_random_dots_within_3px"] if worst else 0.0
    lift_of_worst = (_nb(worst) or 0.0) if worst else 0.0
    worst_unc = max((c["lift_over_random"] or 0.0) for c in uniq["comparisons"]) if uniq["comparisons"] else 0.0

    holdouts = sorted(EVID.glob("h67_holdout_C*.json"))
    hd = None
    for _h in holdouts:
        _d = json.loads(_h.read_text())
        if hd is None:
            hd = _d
        else:
            for _i, _r in _d["instruments"].items():
                if "recipes" not in _r:
                    continue
                hd["instruments"].setdefault(_i, _r)["recipes"].update(_r["recipes"])
    holdout = holdouts[0] if holdouts else EVID / "h67_holdout_C.json"
    nullp = EVID / "h67_null_control.json"
    nl = json.loads(nullp.read_text()) if nullp.exists() else None

    # ---- scientific gate: the emitted recipe must beat the placement null on the same folds ---
    # IR-66-GATE-01: an overlap or gain number is meaningless without the random-placement
    # baseline for the same truth, budget and eligible mask, so the gate is against the null.
    emitted_key = None
    cand_dti = null_dti = None
    if hd is not None and card.get("emission", {}).get("recipe"):
        r_short = card["emission"]["recipe"].split("_")[0]
        emitted_key = (f"{r_short}|k{float(card['emission'].get('kappa_truth_mass', 1.0))}"
                       f"|s{int(card['emission'].get('standoff_px', 2))}")
        inst = next(iter(hd["instruments"]), None)
        rec = hd["instruments"].get(inst, {}).get("recipes", {}).get(emitted_key)
        cand_dti = rec["mean_holdout_dti"] if rec else None
        if nl is not None and inst in nl["instruments"]:
            null_dti = nl["instruments"][inst]["nulls"]["NULL-1_random_eligible"]["mean_dti"]

    gates = {
        "single float32 band": (count == 1 and dtype == "float32",
                                f"count={count} dtype={dtype}"),
        "EPSG:32611 and CRS matches the official reference": (
            crs == ref_crs and str(crs) == "EPSG:32611", f"{crs} vs {ref_crs}"),
        "shape matches the official reference": (shape == ref_shape, f"{shape} vs {ref_shape}"),
        "geotransform matches the official reference": (
            all(abs(a - b) < 1e-6 for a, b in zip(transform, ref_transform)),
            f"{transform} vs {ref_transform}"),
        "all finite values in [0, 1]": (vals.size > 0 and vals.min() >= 0 and vals.max() <= 1,
                                        f"min={vals.min() if vals.size else None} "
                                        f"max={vals.max() if vals.size else None}"),
        "no NaN inside the footprint": (int((~finite & fp).sum()) == 0,
                                        f"nan_inside={int((~finite & fp).sum())} of "
                                        f"{int(fp.sum()):,} reference-mask cells; features-mask "
                                        f"disagreement={fp_disagree}"),
        "NaN only outside the footprint": (int((finite & ~fp).sum()) == 0,
                                           f"finite_outside={int((finite & ~fp).sum())}"),
        "official validator reports no failures and no skipped checks": (
            report["passed"], f"passed={report['passed']} "
            f"failures={report['has_failures']} "
            f"skipped={report.get('skipped_checks_mean_unverified')}"),
        "submission note is at most 140 characters": (
            len(card["submission"]["note"]) <= 140, f"{len(card['submission']['note'])} chars"),
        "rank correlation with every registry raster below 0.90": (
            max_rho <= 0.90, f"max |rho| = {max_rho:.4f} over {len(uniq['comparisons'])} rasters"),
        "no registry raster is duplicated (within-3px and null lift judged per raster)": (
            not dup_rasters,
            f"max within-3px = {max_within3:.4f} (unconditional null lift {worst_unc:.2f}; "
            f"neighbourhood-conditioned null {null_of_worst:.4f}, lift {lift_of_worst:.2f}); "
            f"rasters failing BOTH the 0.70 overlap rule and a 3x neighbourhood-null lift = "
            f"{len(dup_rasters)} of {len(uniq['comparisons'])}"),
        "not byte-identical to any registry raster": (
            sha_twins == 0, f"{sha_twins} sha256 twins; max coincident dots with one raster "
            f"= {max_coincident:,}"),
        "holdout evidence exists for the emitted recipe": (
            hd is not None and cand_dti is not None,
            f"{holdout.name} / {emitted_key}" if (hd and cand_dti is not None)
            else f"missing holdout row for {emitted_key}"),
        "emitted recipe beats the random-placement null on the same folds and budget": (
            cand_dti is not None and null_dti is not None and cand_dti > null_dti,
            (f"HOLDOUT-DTI {cand_dti:.4f} vs null {null_dti:.4f}"
             if (cand_dti is not None and null_dti is not None) else "null control not measured")),
        "run card promotion decision is promote": (
            card.get("promotion_decision") == "promote",
            str(card.get("promotion_decision", "absent"))),
    }
    out["gates"] = {k: {"pass": bool(v[0]), "detail": v[1]} for k, v in gates.items()}
    out["reasons"] = [k for k, v in gates.items() if not v[0]]
    out["cleared"] = not out["reasons"]
    out["raster"] = {"path": tif, "zip": zip_path, "sha256": sha256_file(tif),
                     "zip_sha256": sha256_file(zip_path), "bytes": tif.stat().st_size,
                     "zip_bytes": zip_path.stat().st_size,
                     "emitted": int((arr > 0).sum()), "crs": str(crs), "shape": list(shape),
                     "transform": list(transform), "min": float(vals.min()),
                     "max": float(vals.max()),
                     "nan_outside": int((~finite).sum())}
    out["uniqueness"] = {"n_rasters": len(uniq["comparisons"]), "max_rho": max_rho,
                         "max_within3": max_within3, "max_lift": max_lift,
                         "rows": sorted(uniq["comparisons"],
                                        key=lambda c: -c["frac_cand_dots_within_3px"])[:8]}
    out["holdout"] = hd
    out["validator"] = report
    return out


def download_block(a: dict) -> str:
    if not a.get("card"):
        return """<div class="banner stop"><h2>Download status: NOT AVAILABLE</h2>
<p><b>There is no submission GeoTIFF to download yet.</b> No experiment has cleared the gates,
so nothing is published in <code>docs/downloads/</code>. This is a deliberate, logged outcome,
not an error.</p></div>"""
    c = a["card"]
    r = a["raster"]
    if a["cleared"]:
        rows = "".join(
            f'<tr><th>{html.escape(k)}</th><td><span class="pill ok">PASS</span> '
            f'<span class="small">{html.escape(str(v["detail"]))}</span></td></tr>'
            for k, v in a["gates"].items())
        return f"""<div class="banner go">
<h2>&#9989; DOWNLOAD READY &mdash; OK TO SUBMIT</h2>
<p><b>All {len(a['gates'])} release gates pass on the bytes that are published here.</b>
Re-verified from disk at build time, not copied from an older receipt.</p>
<div class="dl">
<a href="../downloads/{html.escape(r['path'].name)}" download>&#11015; Download the submission .tif</a>
<a class="alt" href="../downloads/{html.escape(r['zip'].name)}" download>&#11015; Download the .zip</a>
</div>
<table class="kv">
<tr><th>file</th><td class="mono">{html.escape(r['path'].name)}</td></tr>
<tr><th>sha256</th><td class="mono">{r['sha256']}</td></tr>
<tr><th>size</th><td>{r['bytes']:,} bytes (zip {r['zip_bytes']:,})</td></tr>
<tr><th>grid</th><td>{r['shape'][0]} &times; {r['shape'][1]}, {r['crs']}, 100 m, single band
float32 &mdash; identical to <code>sample_submission.tif</code></td></tr>
<tr><th>values</th><td>min {r['min']:.4f} &middot; max {r['max']:.4f} &middot;
{r['emitted']:,} pixels &gt; 0 &middot; {r['nan_outside']:,} NaN cells, all outside the footprint</td></tr>
<tr><th>submission name</th><td class="mono">{html.escape(c['submission']['name'])}</td></tr>
<tr><th>note ({len(c['submission']['note'])}/140 chars)</th>
<td class="mono">{html.escape(c['submission']['note'])}</td></tr>
</table>
<h3>Gate detail</h3><table>{rows}</table>
<p class="small">No organizer score is claimed for this file. Nothing has been uploaded by this
repository; uploading is a manual step described in
<a href="executive-summary.html">How to submit</a>.</p>
</div>"""
    fails = "".join(f"<li><b>{html.escape(k)}</b> &mdash; {html.escape(str(v['detail']))}</li>"
                    for k, v in a["gates"].items() if not v["pass"])
    return f"""<div class="banner stop"><h2>&#10060; Download status: NOT CLEARED</h2>
<p>An H67 artifact exists (<code>{html.escape(c['submission']['name'])}</code>) but
<b>{len(a['reasons'])} release gate(s) fail</b>, so it is <b>not</b> published as a download.
Do not upload it.</p><ul>{fails}</ul></div>"""


def holdout_table(a: dict) -> str:
    hd = a.get("holdout")
    if not hd:
        return "<p class='small'>No holdout evidence file found.</p>"
    rows = []
    for inst, r in hd["instruments"].items():
        for key, s in sorted(r["recipes"].items(),
                             key=lambda kv: -(kv[1]["mean_holdout_dti"] or 0)):
            rows.append(
                f"<tr><td>{html.escape(inst)}</td><td class='mono'>{html.escape(key)}</td>"
                f"<td>{html.escape(s['description'])}</td>"
                f"<td>{s['mean_holdout_dti']:.4f}</td>"
                f"<td>{s['ci95'][0]:.4f} &ndash; {s['ci95'][1]:.4f}</td>"
                f"<td>{s['folds']}</td><td>{r['withheld_positive_pixels_pooled']:,}</td>"
                f"<td>{s['mean_emitted']:,.0f}</td></tr>")
    return ("<table><tr><th>instrument</th><th>key</th><th>belief recipe</th>"
            "<th>HOLDOUT-DTI</th><th>95% CI</th><th>folds</th><th>withheld px</th>"
            "<th>dots</th></tr>" + "".join(rows) + "</table>"
            f"<p class='small'>Evaluator: <code>{html.escape(hd['evaluator_version'])}</code>. "
            f"{html.escape(hd['caveat'])}</p>")


def canary_table(a: dict, limit: int = 14) -> str:
    hd = a.get("holdout")
    if not hd:
        return "<p class='small'>No holdout evidence file found.</p>"
    out = []
    for inst, r in hd["instruments"].items():
        rows = sorted(((v["max_auc"] or 0, k) for k, v in r["leakage_canary"].items()),
                      reverse=True)[:limit]
        BAD = '<span class="pill bad">LEAKAGE</span>'
        OK = '<span class="pill ok">ok</span>'
        body = "".join(
            f"<tr><td class='mono'>{html.escape(k)}</td><td>{auc:.3f}</td>"
            f"<td>{BAD if auc > 0.90 else OK}</td></tr>"
            for auc, k in rows)
        flagged = [k for k, v in r["leakage_canary"].items() if v["leakage_flag_auc_gt_0.90"]]
        out.append(f"<h3>{html.escape(inst)}</h3><table><tr><th>layer</th><th>max AUC alone</th>"
                   f"<th>verdict</th></tr>{body}</table>"
                   f"<p class='small'>Flagged above the 0.90 leakage threshold: "
                   f"{html.escape(', '.join(flagged)) if flagged else 'none'}</p>")
    return "".join(out)


def main() -> int:
    DOCS.mkdir(exist_ok=True)
    SITE.mkdir(exist_ok=True)
    DL.mkdir(exist_ok=True)
    (SITE / "assets").mkdir(exist_ok=True)
    (SITE / "assets" / "site.css").write_text(css())
    (DOCS / ".nojekyll").write_text("")

    card_path = newest(str(ART / "run-card-*.json"))
    a = assess(card_path)

    # Publish or withdraw THIS lane's download bytes according to the recomputed verdict.
    # docs/downloads/ is shared with the other lanes on main, so only our own prefix is touched --
    # a blanket *.tif unlink here deleted the session-66 and H67-1 candidates during the merge.
    for f in list(DL.glob("gems66-h67-geophys-maxcov-*.tif")) + \
             list(DL.glob("gems66-h67-geophys-maxcov-*.zip")):
        f.unlink()
    if a["cleared"]:
        shutil.copy2(a["raster"]["path"], DL / a["raster"]["path"].name)
        shutil.copy2(a["raster"]["zip"], DL / a["raster"]["zip"].name)
    (SITE / "DOWNLOADS.md").write_text(
        "# Submission downloads\n\n" +
        (f"**CLEARED:** `{a['raster']['path'].name}` "
         f"(sha256 `{a['raster']['sha256']}`).\n" if a["cleared"] else
         "**Nothing is cleared.** This directory intentionally holds no GeoTIFF.\n") +
        "\nGenerated by `scripts/build_site_h67.py`, which re-validates the artifact from disk\n"
        "before copying it here. Do not add files by hand.\n")

    c = a.get("card") or {}
    # publish the current lane's run card beside the pages so a reviewer can check the verdict
    # against the same JSON the gate read; the historical run_card.json is left untouched
    (DOCS / "data").mkdir(exist_ok=True)
    if a.get("card"):
        (DOCS / "data" / "run-card-h67.json").write_text(
            json.dumps({**a["card"],
                        "release_gates_recomputed_at_build": a["gates"],
                        "cleared_for_download": a["cleared"],
                        "clearing_failures": a["reasons"]}, indent=1))
    h66c_blocks.REL = "../"  # pages render into docs/h67/
    idx = download_block(a) + submission_block_h66c() + f"""
<h2>What this project is</h2>
<p>An auditable pipeline that produces one GeoTIFF of fault predictions for the
<a href="{OFFICIAL}">DOE GEMS Prize</a> (DrivenData competition 306). The scored truth is
<b>faults that are not in the public USGS database</b>, so every design choice here targets
that population rather than the 60,988 labelled pixels we were given.</p>
<p>The single most important measurement in this repository is the structure of the official
metric. It is a <b>budget</b>, not a segmentation score: every emitted pixel costs
&alpha;&nbsp;=&nbsp;0.2 whether or not it earns credit. That is why the emitted file is a sparse
dot set and not a dense probability map. See <a href="method.html">Method &amp; metric</a>.</p>

<h2>This session's finding</h2>
<p><b>95.2% of the USGS SGMC state-geologic-map fault pixels in the study area lie outside the
given catalogue</b> (79,615 of 83,593; 62,122 of them more than 300 m from any catalogue pixel).
The given labels come from the USGS <i>Quaternary</i> fault database and INGENIOUS, so bedrock
geologic-map faults are precisely the population that database omits &mdash; and precisely what an
expert panel would add. No earlier session in this family emitted an SGMC-anchored candidate;
the layer was carried as "proxy only, not used in the factorial".</p>

<h2>Holdout evidence (HOLDOUT-DTI, never an organizer score)</h2>
{holdout_table(a)}

<h2>Leakage canary</h2>
{canary_table(a)}

<h2>Files and provenance</h2>
<table>
<tr><th>input</th><th>source</th></tr>
<tr><td>training_features.tif (19 bands)</td><td>organiser, via hash-pinned mirror
(<a href="{PROBLEM}">problem page</a>)</td></tr>
<tr><td>labels.tif / existing_faults.tif</td><td>organiser, via hash-pinned mirror; the two are
byte-identical (logged as an irregularity)</td></tr>
<tr><td>sample_submission.tif</td><td>organiser grid template &mdash; the only source of the
official CRS, shape and geotransform</td></tr>
<tr><td>SGMC faults</td><td><a href="{SGMC}">USGS state geologic map compilation</a></td></tr>
<tr><td>Quaternary fault traces, wells/springs</td><td><a href="{GDR}">GDR submission 1391</a>,
CC BY 4.0</td></tr>
<tr><td>GeoDAWN radiometrics</td><td><a href="{GEODAWN}">USGS GeoDAWN</a>, DOI 10.5066/P93LGLVQ</td></tr>
<tr><td>LiDAR scarp descriptors</td><td>owner CI from <a href="https://www.usgs.gov/3d-elevation-program">USGS 3DEP 1 m DEM</a>,
aggregated to 100 m &mdash; <b>not</b> the 2&ndash;20 m native scales the original brief asks for</td></tr>
</table>

<h2>Honest limits</h2>
<ul>
<li>The withheld truth in the holdout is a <b>proxy</b>. It is not the organiser's hidden expert set,
so every number here is HOLDOUT-DTI and none is ORGANIZER-CONFIRMED.</li>
<li>The LiDAR lane could not be run at native resolution: only the 100 m aggregate is reachable
from this environment, so the scarplet/Steger/Frangi filters here run at 200&ndash;2000 m, not 2&ndash;20 m.</li>
<li>No organizer receipt ties any byte in this repository to a leaderboard value.</li>
</ul>
"""
    (SITE / "index.html").write_text(page("Download & status", "index.html", idx))

    note = c.get("submission", {}).get("note", "")
    name = c.get("submission", {}).get("name", "")
    exe = f"""<h2>Executive summary &mdash; exactly how to make a submission</h2>
{download_block(a)}
{h66c_exec_block()}
<h3>1. What the portal accepts</h3>
<p>From the <a href="{PROBLEM}">official submission-format rules</a>: a single-band
<b>float32</b> GeoTIFF, <b>EPSG:32611</b> (UTM zone 11N), <b>100 m</b> resolution, the same bounds
as the training data, values in <b>[0, 1]</b>, and null/NaN outside the study area. A
<code>.zip</code> containing one GeoTIFF is also accepted. The portal's own rejection message
<code>Predicted values must be in range [0, 1]</code> means a value fell outside [0, 1] &mdash;
the file published here is checked for exactly that at build time (see the gate table above).</p>
<h3>2. Steps</h3>
<ol>
<li>Click <b>Download the submission .tif</b> at the top of this page. Prefer the .tif; the .zip
is the same bytes zipped.</li>
<li>Check the file's SHA-256 matches <code class="mono">{html.escape(a['raster']['sha256']) if a.get('raster') else 'n/a'}</code>.
If it does not, you downloaded something else &mdash; do not upload it.</li>
<li>Open the <a href="{OFFICIAL}">GEMS Prize</a> on DrivenData and sign in. You must be a
registered participant and have accepted the <a href="{RULES}">rules</a>.</li>
<li>Go to <b>Submissions &rarr; New submission</b>, choose the <code>.tif</code>, and paste the note
below into the optional note field (it is {len(note)}/140 characters).</li>
<li>Submit. The portal scores it and shows the public-leaderboard value. Copy that receipt back
into <code>evidence/</code>; until then no score is claimed here.</li>
</ol>
<div class="note"><b>Submission name:</b> <code class="mono">{html.escape(name)}</code><br>
<b>Note (paste this):</b> <code class="mono">{html.escape(note)}</code></div>
<h3>3. Budget and rules that matter</h3>
<ul>
<li>Up to <b>three feedback submissions per week</b>.</li>
<li>You must choose <b>one</b> submission before the deadline; it is scored in <b>both</b> prize
rounds, and you choose without seeing your private-test result.</li>
<li>The <b>Initial Prize Round</b> is scored against a fixed private set of expert-labelled new
faults. The <b>Final Prize Round</b> re-scores the same file against an <i>expanded</i> label set
built by an expert panel that reviews every team's predictions &mdash; so genuinely new,
defensible fault candidates can pay off twice.</li>
<li>The rules require a narrative disclosure of generative-AI use. This repository's pipeline was
written by an AI agent working from the public competition pages and public USGS/GDR data; say
so truthfully and specifically in your narrative.</li>
</ul>
<h3>4. What is <i>not</i> cleared</h3>
<div class="stop-box">Historical artifacts under <code>artifacts/lidar_lane/</code>,
<code>artifacts/h66-2/</code> and <code>evidence/archives/h66-1/</code> are audit-only. They are
not published here and must not be uploaded.</div>
<h3>5. Links for manual review</h3>
<ul>
<li><a href="{PROBLEM}">Problem description (page 967)</a></li>
<li><a href="{ABOUT}">About / resources (page 968)</a></li>
<li><a href="{RULES}">Full rules</a></li>
<li><a href="{LEADERBOARD}">Leaderboard</a> (values are not mirrored on this site)</li>
<li><a href="{REFSOL}">Official reference solution</a></li>
<li><a href="{TVERSKY}">Tversky index</a> &middot; <a href="{EPSG}">EPSG:32611</a></li>
</ul>
"""
    (SITE / "executive-summary.html").write_text(page("How to submit", "executive-summary.html", exe))

    ts = a.get("holdout") or {}
    results = f"""<h2>Results</h2>
<h3>1. Metric structure, recovered from the official formula</h3>
<p>Because every artifact in the pinned scored mirror is strictly binary
(<code>p &isin; {{0,1}}</code>, asserted before use), the official DTI collapses to</p>
<p class="mono">DTI = T / (0.2 T + 0.2 (N &minus; M) + 0.8 |G|)</p>
<p>with <code>N</code> emitted cells, <code>T</code> = TP<sub>w</sub>, <code>M</code> the emitted
mass that lands within 300 m of truth, and <code>|G|</code> the hidden positive count. Writing
&rho; = T/|G| (kernel-weighted recall) and x = (N&minus;M)/|G| (wasted mass),</p>
<p class="mono">DTI = &rho; / (0.2 &rho; + 0.2 x + 0.8)</p>
<p>Inverting the two scored thinning levels of one belief surface
(<code>h25-1-dotted-h19-5</code> at 60,069 dots &rarr; 0.2477 and 44,090 dots &rarr; 0.2600)
identifies <b>&rho; = 0.2565</b> and <b>x = 0.676</b> for that family, and these two ratios are
invariant to the single nuisance (the wasted-mass fraction). <code>|G|</code> itself is only
bounded (&le; 65,241); that is stated rather than guessed. See
<code>evidence/h67_truth_size.json</code>.</p>
<div class="note"><b>Consequence.</b> There are exactly two levers: raise &rho;, or cut x. Both are
measurable on the holdout. Adding dots to a fixed belief surface only ever lowers DTI, because
each one costs 0.2 whether or not it earns credit.</div>
<h3>2. HOLDOUT-DTI</h3>
{holdout_table(a)}
<h3>3. Leakage canary (every layer alone)</h3>
{canary_table(a)}
<h3>4. Registry uniqueness</h3>
{uniqueness_block(a)}
<h3>5. Scores claimed</h3>
<p><b>None.</b> No ORGANIZER-CONFIRMED score is attached to any byte in this repository. Owner-
and user-reported public values were used only to invert the metric algebra in section 1, and
are labelled as such.</p>
"""
    (SITE / "results.html").write_text(page("Results", "results.html", results))

    hyp = json.loads((ROOT / "docs" / "data" / "h67_hypotheses.json").read_text()) \
        if (ROOT / "docs" / "data" / "h67_hypotheses.json").exists() else {"items": []}
    rows = "".join(
        f"<tr><td>{h['rank']}</td><td><b>{html.escape(h['name'])}</b><br>"
        f"<span class='small'>{html.escape(h['layers'])}</span></td>"
        f"<td>{html.escape(h['signature'])}</td><td>{html.escape(h['why_off_catalogue'])}</td>"
        f"<td>{html.escape(h['named_mimic'])}</td><td>{html.escape(h['differs_from_repo'])}</td>"
        f"<td>{html.escape(h['cost'])}</td><td>{html.escape(h['status'])}</td></tr>"
        for h in hyp.get("items", []))
    (SITE / "hypotheses.html").write_text(page("Hypotheses", "hypotheses.html", f"""
<h2>Ranked hypotheses for this lane</h2>
<p>Ranked by expected DTI improvement per unit of implementation cost. Expected gain is
<b>not</b> quantified before measurement; the holdout decides.</p>
<table><tr><th>#</th><th>name / layers</th><th>physical signature</th>
<th>why it should catch an off-catalogue fault</th><th>named non-fault mimic</th>
<th>how it differs from this repo</th><th>cost</th><th>status</th></tr>{rows}</table>"""))

    (SITE / "method.html").write_text(page("Method & metric", "method.html", f"""
<h2>Metric</h2>
<p>Transcribed from the <a href="{PROBLEM}">official problem page</a>:
<code>k(d) = max(1 &minus; d/300 m, 0)</code>, &alpha; = 0.2, &beta; = 0.8,</p>
<p class="mono">TPw = &Sigma;<sub>g</sub> max<sub>x</sub> p(x) k(d(x,g))<br>
FPw = &Sigma;<sub>x: p&gt;0</sub> p(x) [1 &minus; max<sub>g</sub> k(d(x,g))]<br>
FNw = &Sigma;<sub>g</sub> [1 &minus; max<sub>x</sub> p(x) k(d(x,g))]<br>
DTI = TPw / (TPw + 0.2 FPw + 0.8 FNw)</p>
<p>Our implementation is checked three ways: it equals a literal O(N&middot;M) brute-force
transcription of those formulas to 3.6e-15 on random inputs; the identity
<code>TPw + FNw = |G|</code> holds exactly; and the page's own worked example
(5-pixel vertical truth crossed by a 5-pixel horizontal prediction) reproduces
<b>TPw = 3.00</b> and <b>FNw = 2.00</b> exactly. The page states FPw = 1.89 where a literal
reading of its own formula on a plain 5-pixel cross gives 2.00; that discrepancy is logged as
<code>IR-67-METRIC-01</code> rather than tuned away.</p>
<h2>Emission: greedy maximisation of expected DTI</h2>
<p>Read the belief surface <code>b(x)</code> as independent Bernoulli truth probabilities. Then</p>
<p class="mono">E[TPw](D) = &Sigma;<sub>x</sub> b(x) &middot; max<sub>y&isin;D</sub> k(d(x,y))<br>
E[m<sub>y</sub>] = &int;<sub>0</sub><sup>1</sup> [1 &minus; &prod;<sub>j: k<sub>j</sub>&gt;t</sub> (1 &minus; b(j))] dt<br>
E[DTI](D) = E[TPw] / (0.2 E[TPw] + 0.2 &Sigma;<sub>y&isin;D</sub>(1 &minus; E[m<sub>y</sub>]) + 0.8 &Sigma;b)</p>
<p><code>src/gems67/emit.py</code> adds dots greedily while that ratio rises and <b>stops by
itself</b> at break-even; the budget is only a safety cap. <code>E[m<sub>y</sub>]</code> is exact
under independence (accumulated in log space), and is verified against a 400,000-draw Monte
Carlo in <code>tests/test_h67_emit.py</code>. Because <code>k</code> has 3-pixel support, each
marginal gain is a 7&times;7 local sum.</p>
<h2>Holdout</h2>
<p>Whole fault segments are withheld with a 300 m buffer removed from the <i>visible</i> set only
(<code>src/gems/holdout.py</code>). Every layer that reads the withheld pool is rebuilt from the
visible faults alone, and an assertion fails the run if a withheld pixel is still reachable
through one. Visible faults are masked out of the eligible set pixel-exactly, per protocol.
8-connected components are used as segment IDs and that proxy is disclosed.</p>
<h2>Scale caveat, stated plainly</h2>
<p>The brief asks for 2&ndash;20 m filters on native 1 m LiDAR. The finest reachable product in
this environment is the owner's 100 m aggregate of 3DEP 1 m tiles, so the Frangi/Steger/
structure-tensor scales here are 200&ndash;2000 m. That is a deviation, not a fulfilment, and it
is recorded as such rather than described as the native-resolution method.</p>"""))

    src = [
        ("S01", "Problem description, DOE GEMS Prize", PROBLEM, "official; fetched and transcribed this session"),
        ("S02", "About / resources, page 968", ABOUT, "official"),
        ("S03", "Leaderboard", LEADERBOARD, "official; NO VALUES MIRRORED, no monitoring"),
        ("S04", "Rules", RULES, "official"),
        ("S05", "Reference solution (Lipor)", REFSOL, "official; cloned and read this session"),
        ("S06", "USGS GeoDAWN data release", GEODAWN, "DOI 10.5066/P93LGLVQ"),
        ("S07", "USGS SGMC state geologic map compilation", SGMC, "public domain"),
        ("S08", "GDR submission 1391 (INGENIOUS / wells & springs)", GDR, "CC BY 4.0"),
        ("S09", "EPSG:32611", EPSG, "coordinate reference system definition"),
        ("S10", "Tversky index", TVERSKY, "metric background"),
        ("S11", "USGS 3DEP", "https://www.usgs.gov/3d-elevation-program", "public domain; 1 m tiles"),
        ("S12", "Frangi et al. 1998, MICCAI, LNCS 1496:130-137", "https://doi.org/10.1007/BFb0056195", "vesselness"),
        ("S13", "Steger 1998, IEEE TPAMI 20(2):113-125", "https://doi.org/10.1109/34.659930", "sub-pixel lines"),
        ("S14", "Sare & Hilley 2018, JOSS", "https://doi.org/10.21105/joss.01066", "scarplet"),
    ]
    rows = "".join(f"<tr><td>{i}</td><td>{html.escape(t)}</td>"
                   f"<td class='mono'><a href='{html.escape(u)}'>{html.escape(u)}</a></td>"
                   f"<td>{html.escape(s)}</td></tr>" for i, t, u, s in src)
    (SITE / "sources.html").write_text(page("Sources", "sources.html", f"""
<h2>Sources used, with status</h2>
<table><tr><th>id</th><th>what</th><th>link</th><th>status</th></tr>{rows}</table>
<p class="small">Competition bytes are login-walled at drivendata.org. The only copies used here
are owner-supplied public GitHub blobs pinned by SHA-256 in
<code>registry/data_manifest.json</code> and re-verified by
<code>scripts/fetch_mirrors.py</code> on every run. A matching hash proves mirror consistency,
not organiser authentication.</p>"""))

    irr = [
        ("IR-67-METRIC-01", "The official page's worked example states FPw = 1.89; a literal "
         "reading of its own formula on the 5-pixel cross it depicts gives exactly 2.00. TPw and "
         "FNw reproduce exactly. Our implementation follows the formula, not the figure.", "open"),
        ("IR-67-LABEL-01", "labels.tif and existing_faults.tif are byte-identical "
         "(sha256 7ba308cc&hellip;). The competition ships the same raster under two names.", "open"),
        ("IR-67-SAMPLE-01", "sample_submission.tif is described on the problem page as predicting "
         "'total fault absence', but 60,988 of its cells equal 1 and they sit exactly on the "
         "labelled catalogue. It is usable only as a grid template, never as a baseline.", "open"),
        ("IR-67-MANIFEST-01", "registry/data_manifest.json carries two entries with "
         "repo/ref/sha256 = null (the 10 m topo stack and the LiDAR sidecar). They are "
         "intentionally unpinned; this session does not use either layer.", "open"),
        ("IR-67-SCALE-01", "The requested 2-20 m native-resolution LiDAR filters cannot be run "
         "here: raw 1 m 3DEP tiles are not reachable from this sandbox, so the filters run at "
         "200-2000 m on the 100 m aggregate. Disclosed, not presented as the native method.", "open"),
        ("IR-67-HOLDOUT-01", "With a 300 m segment buffer, a dot placed exactly on a visible "
         "fault can never score, which drove two early recipes to DTI = 0.0000. Fixed by masking "
         "visible faults out of the eligible set pixel-exactly, as the protocol specifies.", "fixed"),
        ("IR-67-LEAK-01", "The first version of the fold-dependent SGMC columns was inverted and "
         "reproduced the withheld truth exactly (distance 0 at every withheld pixel). The "
         "in-fold assertion caught it before any number was reported.", "fixed"),
    ]
    rows = "".join(f"<tr><td class='mono'>{i}</td><td>{html.escape(d)}</td>"
                   f"<td><span class='pill {'ok' if s == 'fixed' else 'warn'}'>{s}</span></td></tr>"
                   for i, d, s in irr)
    (SITE / "irregularities.html").write_text(page("Irregularities", "irregularities.html", f"""
<h2>Irregularity register</h2><table><tr><th>id</th><th>what</th><th>status</th></tr>{rows}</table>"""))

    (SITE / "run-card.html").write_text(page("Run card", "run-card.html", f"""
<h2>Run card</h2><pre class="mono">{html.escape(json.dumps(c, indent=1) if c else '{}')}</pre>"""))

    print(f"site built: cleared={a['cleared']}  reasons={a['reasons']}")
    return 0


def uniqueness_block(a: dict) -> str:
    u = a.get("uniqueness")
    if not u or not u["rows"]:
        return "<p class='small'>No registry comparison recorded.</p>"
    rows = "".join(
        f"<tr><td class='mono'>{html.escape(r['raster'])}</td>"
        f"<td>{r['spearman_rho_surface']:.4f}</td>"
        f"<td>{r['frac_cand_dots_within_3px']:.4f}</td>"
        f"<td>{r['frac_random_dots_within_3px']:.4f}</td>"
        f"<td>{(r['lift_over_random'] or 0):.2f}</td>"
        f"<td>{r['other_dot_count']:,}</td></tr>" for r in u["rows"])
    return (f"<p>Compared against <b>{u['n_rasters']}</b> reachable prior rasters "
            f"(60 registry + 12 scored mirrors). Stop thresholds: |&rho;| &gt; 0.90, or "
            f"&gt; 70% of candidate dots within 3 px of one raster's dots.</p>"
            f"<p class='small'>The random-null column is essential: a registry raster with "
            f"300,000 dots covers so much of the footprint that a <i>uniformly random</i> dot set "
            f"already lands within 3 px of it most of the time. Only the lift above that null is "
            f"evidence of lane drift. Worst rows shown.</p>"
            f"<table><tr><th>registry raster</th><th>Spearman &rho; (surface)</th>"
            f"<th>cand dots within 3 px</th><th>random null</th><th>lift</th>"
            f"<th>its dots</th></tr>{rows}</table>")


if __name__ == "__main__":
    raise SystemExit(main())

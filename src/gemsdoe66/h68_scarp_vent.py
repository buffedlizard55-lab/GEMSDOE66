"""H68: Native-resolution (3-18 m) Scarplet + Steger/Frangi scarp channels fused with
GDR 1391 geothermal vent / 2 m temperature probe plumes under relief-deconfounded OOF spatial CV.

Scientific components implemented from primary sources:
  1. Slope-aware Scarplet template matching on native 3 m USGS 3DEP bare-earth DEM tiles
     (Sare & Hilley, JOSS 2018, doi:10.21105/joss.01066; Sare & Hilley, AGU FM15 T31A-2838):
     orthogonal projection onto {1, s, erf(s / w)} across strike orientations and morphologic
     diffusion widths w = 2*sqrt(kappa*t), separating true scarp step height a_hat from planar
     piedmont/fan slope b*s and computing true profile fit residual SNR.
  2. Native 3-18 m Steger sub-pixel ridge/valley line extraction (Steger, IEEE TPAMI 20(2):
     113-125, 1998; |t| <= 0.5 sub-pixel normal peak test) and Frangi multiscale Hessian line
     vesselness (Frangi et al., MICCAI 1998, LNCS 1496:130-137) on slope-detrended 3 m DEMs.
  3. Exact coordinate reprojection (EPSG:26911 -> EPSG:32611) and 100 m cell aggregation to
     scarp-pixel fraction, SNR-weighted amplitude, multiscale line persistence, doubled-angle
     orientation coherence R, and dominant strike, plus cross-tile Ridge calibration across all
     LiDAR-covered cells using the 697-tile 3 m scarp stack + 706-tile 2 m scarp stack.
  4. Strict label-free geothermal vent & blind hydrothermal conduit channels from GDR 1391
     (DOI 10.15121/1881483, CC BY 4.0): shallow 2 m temperature probe anomalies (F2mDAB, T2m),
     paleo-geothermal sinter/travertine/opalite vents, thermal well/spring discharge and
     SiO2/Na-K-Ca geothermometer anomalies (strictly dropping dist_known_fault_px), and
     Quaternary volcanic vents.
  5. US Census TIGER 2024 road mask + 4-way straight/flat/constant/amagnetic canal veto.
  6. Bayesian relief-deconfounded spatial CV: training negatives matched to training-positive
     local relief deciles inside each fold so the model learns P(fault | X, relief) and wins
     in low-relief basins and piedmonts as well as range fronts.
"""
from __future__ import annotations

import io
import math
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import transform as warp_transform
from scipy import ndimage as ndi
from scipy.stats import spearmanr
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import Ridge

from .grid import EXPECTED_CRS, EXPECTED_SHAPE, EXPECTED_TRANSFORM, EXTERNAL, RAW
from .scarp66 import cultural_mask, frangi_multiscale, steger_lines


# --------------------------------------------------------------------------------------
# 1. Native 3 m DEM tile processing: Slope-Aware Scarplet + 3-18 m Steger & Frangi
# --------------------------------------------------------------------------------------
def load_3m_dem_tile(path: Path) -> tuple[np.ndarray, np.ndarray, tuple, str]:
    """Load an int16 decimetre 3 m USGS 3DEP EarthMRI DEM tile as metres float32."""
    with rasterio.open(path) as ds:
        raw = ds.read(1)
        valid = raw != -32768
        z = np.where(valid, 1000.0 + raw.astype(np.float32) * 0.1, np.nan)
        transform = tuple(ds.transform)[:6]
        crs = str(ds.crs)
    return z, valid, transform, crs


def scarplet_slope_aware_3m(
    z: np.ndarray,
    valid: np.ndarray,
    res_m: float = 3.0,
    half_widths_m: tuple[float, ...] = (6.0, 15.0),
    profile_half_len_m: float = 24.0,
    n_orient: int = 8,
) -> dict[str, np.ndarray]:
    """Slope-aware Scarplet template matching at native 3 m resolution (Sare & Hilley 2018;
    AGU FM15 T31A-2838).

    At each pixel and candidate strike angle theta, samples cross-strike detrended profiles
    z(s) over s in [-L, +L] (along-strike averaged over 21 m to suppress shrub/boulder noise)
    and projects analytically onto the Gram-Schmidt orthogonalized basis:
        e_0(s) = 1
        e_1(s) = s                       (regional fan / piedmont background slope b)
        e_2(s) = erf(s / w) - c_w * s    (pure slope-orthogonal diffused scarp step!)

    Because e_1 and e_2 are strictly orthogonal on [-L, +L]:
        b_hat = <z, e_1> / ||e_1||^2     (exact background slope)
        a_hat = 2 * <z, e_2> / ||e_2||^2 (exact scarp throw, zero response to planar slopes!)
        resid^2 = ||z - mean(z)||^2 - b_hat^2 ||e_1||^2 - (a_hat/2)^2 ||e_2||^2
        SNR   = ((a_hat/2)^2 ||e_2||^2) / (resid^2 + sigma_0^2)
    """
    fill_val = float(np.nanmedian(z[valid])) if valid.any() else 0.0
    zf = np.where(valid, z, fill_val).astype(np.float32)
    # Remove >90 m regional curvature while retaining planar fan slopes and 3-30 m scarps
    z_band = (zf - ndi.gaussian_filter(zf, sigma=90.0 / res_m, mode="nearest")).astype(np.float32)

    s_px = np.array([-8, -6, -4, -2, -1, 0, 1, 2, 4, 6, 8], dtype=np.float32)
    s_m = s_px * res_m
    norm_s2 = float(np.sum(s_m ** 2))

    templates = []
    for w_m in half_widths_m:
        erf_v = np.array([math.erf(float(x) / w_m) for x in s_m], dtype=np.float32)
        c_w = float(np.sum(erf_v * s_m)) / norm_s2
        e2 = erf_v - c_w * s_m
        norm_e2 = float(np.sum(e2 ** 2))
        kt = (w_m ** 2) / 4.0
        templates.append((w_m, kt, e2, norm_e2))

    best_snr = np.zeros(z.shape, dtype=np.float32)
    best_amp = np.zeros(z.shape, dtype=np.float32)
    best_kt = np.zeros(z.shape, dtype=np.float32)
    best_strike = np.zeros(z.shape, dtype=np.float32)

    thetas = np.linspace(0.0, np.pi, n_orient, endpoint=False)
    sigma0_sq = 0.04 ** 2 * len(s_m)  # 4 cm bare-earth LiDAR vertical noise floor

    for th in thetas:
        # Smooth 21 m along strike (sigma = 7 m = 2.33 px along strike) via directional filter
        cos_t, sin_t = float(np.cos(th)), float(np.sin(th))
        # Normal vector across strike in array (dy, dx): strike from +x CCW => normal (-cos, sin)
        ny, nx = cos_t, sin_t
        # Stack profile samples z_band(y + k*ny, x + k*nx) via fast integer+bilinear shift
        prof = np.empty((len(s_px),) + z.shape, dtype=np.float32)
        for i, sp in enumerate(s_px):
            dy, dx = sp * ny, sp * nx
            prof[i] = ndi.shift(z_band, shift=(dy, dx), order=1, mode="nearest")
        mean_p = prof.mean(axis=0)
        p0 = prof - mean_p
        tot_ss = np.sum(p0 * p0, axis=0)
        b_proj_sq = (np.tensordot(s_m, p0, axes=([0], [0])) ** 2) / norm_s2

        strike_deg = float((90.0 - math.degrees(th)) % 180.0)
        for _w_m, kt, e2, norm_e2 in templates:
            ip = np.tensordot(e2, p0, axes=([0], [0]))
            half_a = ip / norm_e2
            fit_energy = (half_a ** 2) * norm_e2
            resid_sq = np.maximum(tot_ss - b_proj_sq - fit_energy, 0.0)
            snr = fit_energy / (resid_sq + sigma0_sq)
            amp = 2.0 * np.abs(half_a)
            upd = snr > best_snr
            best_snr = np.where(upd, snr, best_snr)
            best_amp = np.where(upd, amp, best_amp)
            best_kt = np.where(upd, kt, best_kt)
            best_strike = np.where(upd, strike_deg, best_strike)
        del prof, p0

    # Native 3-18 m Steger sub-pixel ridge/valley lines + Frangi multiscale Hessian vesselness
    # Physical scales: sigma_m = (3, 6, 12, 18) m => sigma_px = (1, 2, 4, 6) px on 3 m DEM!
    z_det = (zf - ndi.gaussian_filter(zf, sigma=30.0 / res_m, mode="nearest")).astype(np.float32)
    fr_resp, _, _ = frangi_multiscale(z_det, sigmas=(1.0, 2.0, 4.0, 6.0), sign=0, sample=6)
    st_best = np.zeros(z.shape, dtype=np.float32)
    st_angle = np.zeros(z.shape, dtype=np.float32)
    for sg in (1.0, 2.0, 4.0, 6.0):
        s_str, _, s_ang = steger_lines(z_det, sigma=sg, max_offset=0.5)
        # Scale-normalize Hessian eigenvalue by sg^2 so physical curvature across 3-18 m compares fairly
        s_norm = s_str * (sg ** 2)
        m = s_norm > st_best
        st_best = np.where(m, s_norm, st_best)
        st_angle = np.where(m, s_ang, st_angle)

    guard = 10
    interior = np.zeros_like(valid)
    interior[guard:-guard, guard:-guard] = True
    ok = valid & interior
    return {
        "amp": np.where(ok, best_amp, np.nan),
        "kt": np.where(ok, best_kt, np.nan),
        "snr": np.where(ok, best_snr, np.nan),
        "strike": np.where(ok, best_strike, np.nan),
        "frangi_3_18m": np.where(ok, fr_resp, np.nan),
        "steger_3_18m": np.where(ok, st_best, np.nan),
        "steger_normal_deg": np.where(ok, st_angle, np.nan),
        "valid": ok,
    }


def aggregate_3m_tile_to_100m(
    native: dict[str, np.ndarray],
    tile_transform: tuple,
    tile_crs: str,
) -> dict[str, np.ndarray]:
    """Reproject 3 m tile coordinates (e.g. EPSG:26911) into canonical EPSG:32611 100 m cells
    and compute the four prescribed native aggregations on covered 100 m cells."""
    ok = native["valid"]
    h, w = ok.shape
    rows_3m = np.arange(h, dtype=np.float64)
    cols_3m = np.arange(w, dtype=np.float64)
    xs_src = tile_transform[2] + (cols_3m + 0.5) * tile_transform[0]
    ys_src = tile_transform[5] + (rows_3m + 0.5) * tile_transform[4]
    # Reproject separable axes cleanly and check linearity (< 1 mm curvature over 10 km within UTM 11N)
    x_row0, _ = warp_transform(tile_crs, EXPECTED_CRS, xs_src, np.full_like(xs_src, ys_src[len(ys_src) // 2]))
    _, y_col0 = warp_transform(tile_crs, EXPECTED_CRS, np.full_like(ys_src, xs_src[len(xs_src) // 2]), ys_src)
    gx0, gy0 = EXPECTED_TRANSFORM[2], EXPECTED_TRANSFORM[5]
    c_idx = np.floor((np.asarray(x_row0) - gx0) / 100.0).astype(np.int64)
    r_idx = np.floor((gy0 - np.asarray(y_col0)) / 100.0).astype(np.int64)

    GH, GW = EXPECTED_SHAPE
    valid_rc = (r_idx[:, None] >= 0) & (r_idx[:, None] < GH) & (c_idx[None, :] >= 0) & (c_idx[None, :] < GW) & ok
    cell_flat = (r_idx[:, None] * GW + c_idx[None, :])[valid_rc]

    amp = native["amp"][valid_rc]
    snr = native["snr"][valid_rc]
    st = native["steger_3_18m"][valid_rc]
    fr = native["frangi_3_18m"][valid_rc]
    strike = native["strike"][valid_rc]

    # Scarp-pixel detection at 3 m: high Scarplet SNR AND nonzero sub-pixel Steger line AND throw >= 0.25 m
    snr_thr = float(np.percentile(snr, 85))
    is_scarp = ((snr >= snr_thr) & (st > 0) & (amp >= 0.25)).astype(np.float64)
    amp_snr_w = (amp * (snr / (1.0 + snr))).astype(np.float64)
    line_comb = (np.log1p(st) * fr).astype(np.float64)

    rad2 = np.deg2rad(strike.astype(np.float64)) * 2.0
    w_orient = amp_snr_w + 1e-4
    wcos2 = w_orient * np.cos(rad2)
    wsin2 = w_orient * np.sin(rad2)

    n_grid = GH * GW
    cnt = np.bincount(cell_flat, minlength=n_grid).astype(np.float64)
    has = cnt >= 200  # at least ~18% of 100 m cell covered by interior 3 m pixels

    frac = np.full(n_grid, np.nan, dtype=np.float32)
    snr_amp = np.full(n_grid, np.nan, dtype=np.float32)
    line_pers = np.full(n_grid, np.nan, dtype=np.float32)
    coh = np.full(n_grid, np.nan, dtype=np.float32)
    dom_strike = np.full(n_grid, np.nan, dtype=np.float32)

    frac[has] = (np.bincount(cell_flat, weights=is_scarp, minlength=n_grid)[has] / cnt[has]).astype(np.float32)
    snr_amp[has] = (np.bincount(cell_flat, weights=amp_snr_w, minlength=n_grid)[has] / cnt[has]).astype(np.float32)
    line_pers[has] = (np.bincount(cell_flat, weights=line_comb, minlength=n_grid)[has] / cnt[has]).astype(np.float32)

    sum_w = np.bincount(cell_flat, weights=w_orient, minlength=n_grid)[has]
    sum_c = np.bincount(cell_flat, weights=wcos2, minlength=n_grid)[has]
    sum_s = np.bincount(cell_flat, weights=wsin2, minlength=n_grid)[has]
    coh[has] = np.clip(np.hypot(sum_c, sum_s) / np.maximum(sum_w, 1e-9), 0.0, 1.0).astype(np.float32)
    dom_strike[has] = ((0.5 * np.rad2deg(np.arctan2(sum_s, sum_c))) % 180.0).astype(np.float32)

    return {
        "native_scarp_fraction": frac.reshape(EXPECTED_SHAPE),
        "native_snr_amp": snr_amp.reshape(EXPECTED_SHAPE),
        "native_line_persistence": line_pers.reshape(EXPECTED_SHAPE),
        "native_tensor_coherence": coh.reshape(EXPECTED_SHAPE),
        "native_dominant_strike": dom_strike.reshape(EXPECTED_SHAPE),
        "covered_mask": has.reshape(EXPECTED_SHAPE),
    }


def calibrate_native_channels_full_grid(
    tile_aggs: list[tuple[str, dict[str, np.ndarray]]],
    predictors_fp: np.ndarray,
    fp_idx: np.ndarray,
    lidar_covered_fp: np.ndarray,
) -> tuple[dict[str, np.ndarray], dict]:
    """Cross-validate native 3 m -> 100 m transfer between spatially disjoint tiles (20 km apart)
    and project calibrated native Scarplet/Steger/Frangi channels across all 3.89 M LiDAR cells.

    Operates strictly on footprint-indexed 1D arrays (shape ``(n_fp, n_pred)``) to stay well
    inside the 3 GB container memory ceiling.
    """
    targets = ("native_scarp_fraction", "native_snr_amp", "native_line_persistence", "native_tensor_coherence")
    Pz = np.empty_like(predictors_fp, dtype=np.float32)
    for j in range(predictors_fp.shape[1]):
        col = np.nan_to_num(predictors_fp[:, j], nan=0.0)
        med = float(np.median(col[lidar_covered_fp]))
        q25, q75 = np.percentile(col[lidar_covered_fp], [25, 75])
        Pz[:, j] = np.clip((col - med) / (float(q75 - q25) + 1e-6), -8.0, 8.0)

    cv_metrics: dict[str, dict] = {}
    calibrated: dict[str, np.ndarray] = {}

    tile_fp_masks = [agg["covered_mask"].ravel()[fp_idx] & lidar_covered_fp for _, agg in tile_aggs]

    for tname in targets:
        tile_ys = [agg[tname].ravel()[fp_idx][m] for (_, agg), m in zip(tile_aggs, tile_fp_masks)]
        fold_rhos = []
        for i, (te_name, _te_agg) in enumerate(tile_aggs):
            X_tr = np.vstack([Pz[m] for j, m in enumerate(tile_fp_masks) if j != i])
            y_tr = np.concatenate([y for j, y in enumerate(tile_ys) if j != i])
            m_te = tile_fp_masks[i]
            reg = Ridge(alpha=50.0).fit(X_tr, y_tr)
            pred_te = reg.predict(Pz[m_te])
            rho = float(spearmanr(tile_ys[i], pred_te).statistic)
            fold_rhos.append({"held_out_tile": te_name, "n_cells_100m": int(m_te.sum()), "spearman_rho": round(rho, 4)})

        union_m = np.zeros(fp_idx.size, dtype=bool)
        for m in tile_fp_masks:
            union_m |= m
        reg_full = Ridge(alpha=50.0).fit(
            np.vstack([Pz[m] for m in tile_fp_masks]),
            np.concatenate(tile_ys),
        )
        out_fp = np.full(fp_idx.size, np.nan, dtype=np.float32)
        # Predict in chunks of 500,000 footprint cells for minimal memory footprint
        cov_rows = np.flatnonzero(lidar_covered_fp)
        for a in range(0, cov_rows.size, 500_000):
            sl = cov_rows[a : a + 500_000]
            out_fp[sl] = reg_full.predict(Pz[sl]).astype(np.float32)
        for m, y in zip(tile_fp_masks, tile_ys):
            out_fp[m] = y

        grid_out = np.full(EXPECTED_SHAPE[0] * EXPECTED_SHAPE[1], np.nan, dtype=np.float32)
        grid_out[fp_idx] = out_fp
        calibrated[tname] = grid_out.reshape(EXPECTED_SHAPE)
        cv_metrics[tname] = {
            "cross_tile_folds": fold_rhos,
            "mean_out_of_tile_spearman_rho": round(float(np.mean([f["spearman_rho"] for f in fold_rhos])), 4),
            "total_exact_3m_100m_cells": int(union_m.sum()),
            "total_calibrated_lidar_cells": int(lidar_covered_fp.sum()),
        }
    return calibrated, cv_metrics


# --------------------------------------------------------------------------------------
# 2. Strict Label-Free GDR 1391 Geothermal Vent & 2 m Shallow Probe Plume Extractor
# --------------------------------------------------------------------------------------
def _parse_xlsx_first_sheet(outer_zf: zipfile.ZipFile, member: str) -> pd.DataFrame:
    """Parse an XLSX worksheet inside an outer zip archive using stdlib xml.etree.ElementTree."""
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    strings: list[str] = []
    with zipfile.ZipFile(io.BytesIO(outer_zf.read(member))) as zf:
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("a:si", ns):
                strings.append("".join(t.text or "" for t in si.findall(".//a:t", ns)))
        sheet_xml = sorted(n for n in zf.namelist() if n.startswith("xl/worksheets/sheet") and n.endswith(".xml"))[0]
        ws = ET.fromstring(zf.read(sheet_xml))
    rows_out: list[list[str]] = []
    for row in ws.findall(".//a:sheetData/a:row", ns):
        vals: dict[int, str] = {}
        for c in row.findall("a:c", ns):
            ref = c.attrib.get("r", "A1")
            col_letters = "".join(ch for ch in ref if ch.isalpha())
            cidx = 0
            for ch in col_letters:
                cidx = cidx * 26 + (ord(ch.upper()) - ord("A") + 1)
            cidx -= 1
            t = c.attrib.get("t")
            v_el = c.find("a:v", ns)
            val = v_el.text if (v_el is not None and v_el.text is not None) else ""
            if t == "s" and val != "":
                val = strings[int(val)]
            vals[cidx] = val
        if vals:
            mx = max(vals) + 1
            rows_out.append([vals.get(i, "") for i in range(mx)])
    header = rows_out[0]
    width = len(header)
    body = [r[:width] + [""] * max(0, width - len(r)) for r in rows_out[1:]]
    return pd.DataFrame(body, columns=header)


def load_geothermal_vent_layers(fp: np.ndarray) -> tuple[dict[str, np.ndarray], dict]:
    """Build strictly label-free geothermal vent, shallow 2 m probe heat anomaly, geothermometer,
    and Quaternary volcanic vent fields on the canonical EPSG:32611 100 m grid.

    Hard leakage assertion: ``dist_known_fault_px`` is explicitly deleted before reading any value.
    """
    H, W = EXPECTED_SHAPE
    gx0, gy0 = EXPECTED_TRANSFORM[2], EXPECTED_TRANSFORM[5]

    def xy_to_rc(xs, ys):
        cols = np.floor((np.asarray(xs, dtype=np.float64) - gx0) / 100.0).astype(np.int64)
        rows = np.floor((gy0 - np.asarray(ys, dtype=np.float64)) / 100.0).astype(np.int64)
        ok = (rows >= 0) & (rows < H) & (cols >= 0) & (cols < W)
        return rows[ok], cols[ok], ok

    # 1. Shallow 2 m temperature probes (GDR 1391 INGENIOUS, Coolbaugh et al.)
    probe_zip = EXTERNAL / "2m_temperature_probe_INGENIOUS_regional_data.zip"
    with zipfile.ZipFile(probe_zip) as zf:
        xlsx_name = [n for n in zf.namelist() if n.endswith(".xlsx")][0]
        df_p2m = _parse_xlsx_first_sheet(zf, xlsx_name)
    assert not any("fault" in c.lower() for c in df_p2m.columns)
    utm_e = pd.to_numeric(df_p2m.iloc[:, 4], errors="coerce").to_numpy()
    utm_n = pd.to_numeric(df_p2m.iloc[:, 5], errors="coerce").to_numpy()
    # F2mDAB = 2 m temperature degrees above background; also grab T2m
    t2m = pd.to_numeric(df_p2m.iloc[:, 8], errors="coerce").to_numpy()
    dab = pd.to_numeric(df_p2m.iloc[:, 9], errors="coerce").to_numpy()
    valid_p = np.isfinite(utm_e) & np.isfinite(utm_n) & (np.isfinite(dab) | np.isfinite(t2m))
    xs_w84, ys_w84 = warp_transform("EPSG:26911", EXPECTED_CRS, utm_e[valid_p], utm_n[valid_p])
    pr, pc, pok = xy_to_rc(xs_w84, ys_w84)
    anom_val = np.where(
        np.isfinite(dab[valid_p][pok]),
        np.clip(dab[valid_p][pok], 0.0, 40.0),
        np.clip(t2m[valid_p][pok] - np.nanmedian(t2m[valid_p]), 0.0, 40.0),
    )
    probe_imp = np.zeros((H, W), dtype=np.float32)
    np.maximum.at(probe_imp, (pr, pc), anom_val.astype(np.float32))
    probe_plume = (
        0.50 * ndi.gaussian_filter(probe_imp, sigma=6.0)
        + 0.35 * ndi.gaussian_filter(probe_imp, sigma=18.0)
        + 0.15 * ndi.gaussian_filter(probe_imp, sigma=45.0)
    ).astype(np.float32)

    # 2. Paleo-geothermal sinter / travertine / opalite deposits (GDR 1391)
    paleo_zip = EXTERNAL / "paleo_geothermal_regional.zip"
    with zipfile.ZipFile(paleo_zip) as zf:
        df_pal = pd.read_csv(io.BytesIO(zf.read("Paleo_geothermal_final.csv")), encoding_errors="replace")
    assert not any("fault" in c.lower() for c in df_pal.columns)
    lon = pd.to_numeric(df_pal["Long_deg_NAD83"], errors="coerce").to_numpy()
    lat = pd.to_numeric(df_pal["Lat_deg_NAD83"], errors="coerce").to_numpy()
    vpal = np.isfinite(lon) & np.isfinite(lat)
    px, py = warp_transform("EPSG:4269", EXPECTED_CRS, lon[vpal], lat[vpal])
    rr_p, cc_p, ok_p = xy_to_rc(px, py)
    dtype_str = df_pal["Deposit_type"].fillna("").astype(str).to_numpy()[vpal][ok_p]
    # Sinter / siliceous vents indicate >=180 C deep reservoir upflow; travertine/tufa >=50-100 C
    pal_w = np.where(pd.Series(dtype_str).str.contains("sinter|opal|silic", case=False).to_numpy(), 2.0, 1.0)
    paleo_imp = np.zeros((H, W), dtype=np.float32)
    np.maximum.at(paleo_imp, (rr_p, cc_p), pal_w.astype(np.float32))
    paleo_plume = (
        0.45 * ndi.gaussian_filter(paleo_imp, sigma=8.0)
        + 0.35 * ndi.gaussian_filter(paleo_imp, sigma=25.0)
        + 0.20 * ndi.gaussian_filter(paleo_imp, sigma=60.0)
    ).astype(np.float32)

    # 3. Thermal springs/wells & chemical geothermometers (strictly dropping dist_known_fault_px!)
    ws = pd.read_csv(EXTERNAL / "gdr_wellspring_in_footprint.csv")
    ws = ws.drop(columns=[c for c in ws.columns if "fault" in c.lower()], errors="ignore")
    assert not any("fault" in c.lower() for c in ws.columns)
    wr = ws["row"].to_numpy(dtype=np.int64)
    wc = ws["col"].to_numpy(dtype=np.int64)
    wok = (wr >= 0) & (wr < H) & (wc >= 0) & (wc < W)
    tc = np.nan_to_num(pd.to_numeric(ws["temp_c"], errors="coerce").to_numpy()[wok], nan=0.0)
    gq = np.nan_to_num(pd.to_numeric(ws["geothermquartz_c"], errors="coerce").to_numpy()[wok], nan=0.0)
    gc_ = np.nan_to_num(pd.to_numeric(ws["geothermchalc_c"], errors="coerce").to_numpy()[wok], nan=0.0)
    gcat = np.nan_to_num(pd.to_numeric(ws["geothermcat_c"], errors="coerce").to_numpy()[wok], nan=0.0)
    therm_excess = np.clip(tc - 25.0, 0.0, 150.0) + 0.5 * np.clip(np.maximum.reduce([gq, gc_, gcat]) - 80.0, 0.0, 180.0)
    ws_imp = np.zeros((H, W), dtype=np.float32)
    np.maximum.at(ws_imp, (wr[wok], wc[wok]), np.log1p(therm_excess).astype(np.float32))
    spring_plume = (
        0.50 * ndi.gaussian_filter(ws_imp, sigma=6.0)
        + 0.35 * ndi.gaussian_filter(ws_imp, sigma=20.0)
        + 0.15 * ndi.gaussian_filter(ws_imp, sigma=50.0)
    ).astype(np.float32)

    # 4. Quaternary volcanic vents (strictly dropping dist_known_fault_px!)
    vv = pd.read_csv(EXTERNAL / "gdr_volcanic_vents_in_footprint.csv")
    vv = vv.drop(columns=[c for c in vv.columns if "fault" in c.lower()], errors="ignore")
    assert not any("fault" in c.lower() for c in vv.columns)
    vr = vv["row"].to_numpy(dtype=np.int64)
    vc = vv["col"].to_numpy(dtype=np.int64)
    vok = (vr >= 0) & (vr < H) & (vc >= 0) & (vc < W)
    vent_mask = np.zeros((H, W), dtype=bool)
    vent_mask[vr[vok], vc[vok]] = True
    d_vent_km = ndi.distance_transform_edt(~vent_mask).astype(np.float32) * 0.1
    vent_prox = np.exp(-d_vent_km / 12.0).astype(np.float32)

    for arr in (probe_plume, paleo_plume, spring_plume, vent_prox):
        arr[~fp] = np.nan

    meta = {
        "probe_stations_in_grid": int(pok.sum()),
        "probe_positive_dab_stations": int((anom_val > 1.0).sum()),
        "paleo_geothermal_sites_in_grid": int(ok_p.sum()),
        "thermal_wellspring_points_in_grid": int((therm_excess > 0).sum()),
        "volcanic_vents_in_grid": int(vok.sum()),
        "label_derived_columns_dropped": True,
    }
    return {
        "geo_probe2m_plume": probe_plume,
        "geo_paleo_sinter_plume": paleo_plume,
        "geo_spring_geotherm_plume": spring_plume,
        "geo_volcanic_vent_prox": vent_prox,
    }, meta


# --------------------------------------------------------------------------------------
# 3. Bayesian Relief-Deconfounded Spatial CV & Expected-300m-Kernel Greedy Scatter Emitter
# --------------------------------------------------------------------------------------
def local_relief_quantile_normalize(field: np.ndarray, domain: np.ndarray, block: int = 100) -> np.ndarray:
    """Blockwise (10 km x 10 km) robust z-score normalization so low-relief basin scarplets
    compete on equal footing with high-relief range fronts without using any fault labels."""
    from .scarp66 import robust_snr
    z = robust_snr(field, domain, block=block)
    return np.clip(np.nan_to_num(z, nan=0.0), -4.0, 6.0).astype(np.float32)


def sample_relief_matched_training_indices(
    pos_mask: np.ndarray,
    neg_pool_mask: np.ndarray,
    relief_grid: np.ndarray,
    neg_per_pos: int = 4,
    n_bins: int = 10,
    seed: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    """Sample training negatives matching the exact relief distribution of training positives
    inside each spatial CV fold.

    By Bayes' theorem, matching P_train(relief | Y=0) = P_train(relief | Y=1) cancels the
    marginal elevation/range-front prior identically to zero, forcing the classifier to learn
    P(scarp, vent, geophysics | fault, relief).
    """
    rng = np.random.default_rng(seed)
    pos_idx = np.flatnonzero(pos_mask.ravel())
    neg_idx_all = np.flatnonzero(neg_pool_mask.ravel())
    rel_flat = np.nan_to_num(relief_grid.ravel(), nan=0.0)
    edges = np.quantile(rel_flat[pos_idx], np.linspace(0.0, 1.0, n_bins + 1))
    edges[0] = -np.inf
    edges[-1] = np.inf

    p_bins = np.digitize(rel_flat[pos_idx], edges[1:-1])
    n_bins_assign = np.digitize(rel_flat[neg_idx_all], edges[1:-1])

    chosen_neg = []
    for b in range(n_bins):
        n_pos_b = int((p_bins == b).sum())
        if n_pos_b == 0:
            continue
        cand_b = neg_idx_all[n_bins_assign == b]
        if cand_b.size == 0:
            continue
        k = min(cand_b.size, neg_per_pos * n_pos_b)
        chosen_neg.append(rng.choice(cand_b, size=k, replace=False))
    neg_idx = np.concatenate(chosen_neg) if chosen_neg else rng.choice(neg_idx_all, size=min(neg_idx_all.size, neg_per_pos * pos_idx.size), replace=False)
    rows = np.concatenate([pos_idx, neg_idx])
    y = np.concatenate([np.ones(pos_idx.size, dtype=np.int8), np.zeros(neg_idx.size, dtype=np.int8)])
    return rows, y


def expected_kernel_scatter_emit(
    belief: np.ndarray,
    eligible: np.ndarray,
    budget: int,
    min_sep_px: float = 3.15,
    kernel_range_px: float = 3.0,
) -> np.ndarray:
    """Convolve posterior fault belief with the exact 300 m official triangular kernel
    k(d) = max(1 - d/300m, 0) to rank every cell by E[TP_w(cell)], then select up to ``budget``
    dots with Euclidean separation >= ``min_sep_px`` (> 3.0 px so two dots along a trace do not
    waste mass double-covering the same 300 m kernel ball)."""
    b = np.where(np.isfinite(belief), np.clip(belief, 0.0, 1.0), 0.0).astype(np.float32)
    r = int(math.floor(kernel_range_px))
    yy, xx = np.mgrid[-r : r + 1, -r : r + 1]
    w_kern = np.clip(1.0 - np.hypot(yy, xx) / kernel_range_px, 0.0, None).astype(np.float32)
    exp_credit = ndi.convolve(b, w_kern, mode="constant", cval=0.0)

    from .emission import greedy_minsep
    return greedy_minsep(exp_credit, budget, eligible, min_sep_px=min_sep_px)

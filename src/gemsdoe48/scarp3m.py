"""H52-1: linear fault-scarp detector for 2–3 m DEM tiles (USGS 3DEP 1 m, block-averaged).

Physical model (Bucknam & Anderson 1979, Geology 7:11-14; Hanks et al. 1984, JGR 89:5771;
Hilley et al. 2010, GRL doi:10.1029/2009GL042044): a fault scarp is a *step* in an
otherwise smooth surface — the far-field surfaces on both sides are sub-parallel and
vertically separated by the scarp height. The step is *linear* and persists along
strike for hundreds of metres, it faces up- or down- the regional slope (range-front
and piedmont scarps are sub-parallel to contours), and it is anomalous relative to the
roughness of its surroundings. Channel banks and terrace risers run *along* the
regional slope direction; roads and canals are double-edged with no net far-field
offset; bedrock texture has high context roughness.

Per pixel (3 m) we therefore compute, for a set of candidate strike orientations θ:

    Δ_θ(x) = mean of z_d along a strike-parallel line of length L on the + side of x
           − the same on the − side, where z_d = z_6m − z_60m is the detrended surface
           and the two sides are offset ±w perpendicular to θ.

    H(x)   = max_θ |Δ_θ(x)|                      line-persistent scarp height (m)
    θ*(x)  = argmax                              strike
    facing = |cos(angle between the normal to θ* and the regional downslope vector)|
    σ_ctx  = std of z_d within a 150 m window     context roughness (m)
    score  = H · facing^p / (σ_ctx + c)           dimensionless anomaly

Everything is label-free. The catalogue is used only for evaluation.

Known v1 limitations (synthetic tests in tests/test_scarp3m.py):
  * the 60 m regional detrend absorbs ~25 % of a step, so H is an *effective* height;
  * the far-field samples are single perpendicular samples at ±w, so a double-edged trench
    wider than ~6 m (canal, wide road cut) registers like a step if one sample falls in it —
    v2 should require consistent offsets at two baselines (±w and ±2w);
  * grabens / paired antithetic scarps narrower than 2w are partly cancelled.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import gaussian_filter, map_coordinates, uniform_filter


@dataclass(frozen=True)
class ScarpParams:
    res_m: float = 3.0
    sigma_local_m: float = 6.0      # smoothing that keeps a 10 m-wide scarp face
    sigma_regional_m: float = 60.0  # regional surface removed before measuring the step
    half_offset_m: float = 21.0     # ±w: distance of the two far-field windows from the line
    line_length_m: float = 150.0    # along-strike averaging length L
    n_line_samples: int = 11        # samples along L
    n_orient: int = 12              # strike candidates on [0, 180)
    context_window_m: float = 150.0
    facing_power: float = 1.0
    roughness_floor_m: float = 0.15
    slope_floor: float = 0.005      # regional slope below which facing is undefined (flat playa)
    edge_guard_m: float = 150.0     # cells closer than this to the tile edge are flagged invalid


def _shift(a: np.ndarray, dy: float, dx: float) -> np.ndarray:
    """Sub-pixel shift by (dy, dx) pixels with linear interpolation, edge-nearest."""
    h, w = a.shape
    yy, xx = np.indices(a.shape, dtype=np.float32)
    return map_coordinates(a, [yy + dy, xx + dx], order=1, mode="nearest").astype(np.float32)


def line_offset(zd: np.ndarray, theta: float, p: ScarpParams) -> np.ndarray:
    """Mean detrended elevation difference across a strike-parallel line pair at angle theta.

    theta is measured from the +x (east) axis, counter-clockwise in map space; rows increase
    southward so dy = -sin(theta) in array coordinates.
    """
    px = p.res_m
    tx, ty = np.cos(theta), -np.sin(theta)          # along-strike unit vector (array coords)
    nx, ny = -ty, tx                                  # normal
    w = p.half_offset_m / px
    ts = np.linspace(-p.line_length_m / 2, p.line_length_m / 2, p.n_line_samples) / px
    plus = np.zeros_like(zd, dtype=np.float32)
    minus = np.zeros_like(zd, dtype=np.float32)
    for t in ts:
        plus += _shift(zd, t * ty + w * ny, t * tx + w * nx)
        minus += _shift(zd, t * ty - w * ny, t * tx - w * nx)
    return (plus - minus) / float(p.n_line_samples)


def detect(z: np.ndarray, p: ScarpParams = ScarpParams()) -> dict[str, np.ndarray]:
    """Run the detector on an elevation grid (NaN = nodata). Returns float32 layers."""
    valid = np.isfinite(z)
    zf = np.where(valid, z, np.nanmean(z)).astype(np.float32)
    px = p.res_m
    z_loc = gaussian_filter(zf, p.sigma_local_m / px, mode="nearest")
    z_reg = gaussian_filter(zf, p.sigma_regional_m / px, mode="nearest")
    zd = (z_loc - z_reg).astype(np.float32)
    gy, gx = np.gradient(z_reg, px)
    smag = np.hypot(gx, gy)
    ok = smag > p.slope_floor
    ux = np.where(ok, gx / np.where(ok, smag, 1.0), 0.0)   # upslope unit vector (map x)
    uy = np.where(ok, gy / np.where(ok, smag, 1.0), 0.0)   # (array y, i.e. south-positive)

    best = np.zeros_like(zd, dtype=np.float32)
    best_theta = np.zeros_like(zd, dtype=np.float32)
    best_signed = np.zeros_like(zd, dtype=np.float32)
    thetas = np.linspace(0.0, np.pi, p.n_orient, endpoint=False)
    for th in thetas:
        d = line_offset(zd, th, p)
        a = np.abs(d)
        upd = a > best
        best = np.where(upd, a, best)
        best_theta = np.where(upd, th, best_theta)
        best_signed = np.where(upd, d, best_signed)
    # normal to the best strike, in array coordinates
    tx, ty = np.cos(best_theta), -np.sin(best_theta)
    nx, ny = -ty, tx
    facing = np.abs(nx * ux + ny * uy)
    facing = np.where(ok, facing, 0.5)  # flat ground: no facing information
    # context roughness: std of zd in a window
    win = max(3, int(round(p.context_window_m / px)) | 1)
    m1 = uniform_filter(zd, win, mode="nearest")
    m2 = uniform_filter(zd * zd, win, mode="nearest")
    sigma_ctx = np.sqrt(np.maximum(m2 - m1 * m1, 0.0)).astype(np.float32)
    score = best * (facing ** p.facing_power) / (sigma_ctx + p.roughness_floor_m)
    # strike in degrees clockwise from north (geological convention), 0..180
    strike = (90.0 - np.degrees(best_theta)) % 180.0
    out = {
        "height": best, "signed_offset": best_signed, "strike_deg": strike.astype(np.float32),
        "facing": facing.astype(np.float32), "sigma_ctx": sigma_ctx, "score": score.astype(np.float32),
        "valid": valid,
    }
    # edge guard: the regional filter and the line windows are unreliable within ~L/2 + 3σ_reg
    guard = int(round(p.edge_guard_m / px))
    edge = np.zeros_like(valid)
    edge[guard:-guard, guard:-guard] = True
    out["valid"] = valid & edge
    for k in ("height", "score"):
        out[k] = np.where(out["valid"], out[k], 0.0).astype(np.float32)
    return out


def aggregate_to_grid(layer: np.ndarray, valid: np.ndarray, tile_transform, grid_transform,
                      grid_shape: tuple[int, int], how: str = "max") -> tuple[np.ndarray, np.ndarray, tuple]:
    """Aggregate a fine layer onto the official 100 m grid (returns window arrays and offsets)."""
    res = tile_transform[0]
    gres = grid_transform[0]
    x0, y0 = tile_transform[2], tile_transform[5]
    gx0, gy0 = grid_transform[2], grid_transform[5]
    h, w = layer.shape
    # fine pixel -> grid col/row
    xs = x0 + (np.arange(w) + 0.5) * res
    ys = y0 - (np.arange(h) + 0.5) * res
    cols = np.floor((xs - gx0) / gres).astype(np.int64)
    rows = np.floor((gy0 - ys) / gres).astype(np.int64)
    cmin, cmax = int(cols.min()), int(cols.max())
    rmin, rmax = int(rows.min()), int(rows.max())
    oh, ow = rmax - rmin + 1, cmax - cmin + 1
    idx = (rows[:, None] - rmin) * ow + (cols[None, :] - cmin)
    vals = np.where(valid, layer, np.nan).ravel()
    flat = idx.ravel()
    good = np.isfinite(vals)
    if how == "max":
        out = np.full(oh * ow, -np.inf, dtype=np.float64)
        np.maximum.at(out, flat[good], vals[good])
        out[~np.isfinite(out)] = np.nan
    elif how == "mean":
        s = np.zeros(oh * ow); n = np.zeros(oh * ow)
        np.add.at(s, flat[good], vals[good]); np.add.at(n, flat[good], 1)
        out = np.where(n > 0, s / np.maximum(n, 1), np.nan)
    else:
        raise ValueError(how)
    cover = np.zeros(oh * ow); np.add.at(cover, flat[good], 1)
    cover = cover / float((gres / res) ** 2)
    return out.reshape(oh, ow), cover.reshape(oh, ow), (rmin, cmin)

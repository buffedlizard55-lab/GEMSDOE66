"""Explore: reproduce the repository's owner-score anchor with the layers actually present.

Reuses OWNER_SCORES from scripts/calibrate_live.py (no private fork of the score table).
Reports weighted-mean-under-dots for every available layer, Spearman rho vs owner score,
permutation p, and leave-one-out RMSE for the best layers.
"""
from __future__ import annotations
import hashlib, importlib.util, json, sys
from pathlib import Path
import numpy as np, rasterio
from scipy.stats import spearmanr
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT / "registry" / "rasters"

def load_mod(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

cal = load_mod(ROOT / "scripts" / "calibrate_live.py")
OWNER = cal.OWNER_SCORES

with rasterio.open(ROOT/"data/raw/sample_submission.tif") as s:
    fp = np.isfinite(s.read(1))
    print("footprint cells", int(fp.sum()))
with rasterio.open(ROOT/"data/raw/labels.tif") as s:
    lab = s.read(1)
cat = lab > 0
print("catalogue positives", int(cat.sum()))

LAYERS = {
  "rad_K": ("data/raw/external/geodawn_rad_u8.tif", 1),
  "rad_Th": ("data/raw/external/geodawn_rad_u8.tif", 2),
  "rad_U": ("data/raw/external/geodawn_rad_u8.tif", 3),
  "rad_TC": ("data/raw/external/geodawn_rad_u8.tif", 4),
  "ext_ThK": ("data/raw/external/geodawn_extensions_u8.tif", 1),
  "ext_UK": ("data/raw/external/geodawn_extensions_u8.tif", 2),
  "ext_UTh": ("data/raw/external/geodawn_extensions_u8.tif", 3),
  "ext_TMI_up150": ("data/raw/external/geodawn_extensions_u8.tif", 4),
  "sgmc_faults": ("data/raw/external/derived_sgmc_faults_100m_u8.tif", 1),
}
arrs = {}
for nm,(p,b) in LAYERS.items():
    with rasterio.open(ROOT/p) as s:
        arrs[nm] = s.read(b).astype(np.float64)
    print(nm, "footprint mean", float(arrs[nm][fp].mean()))

# collapse byte-identical duplicates exactly as calibrate_live.py does
seen = {}
for p in sorted(REG.glob("*.tif")):
    if p.name not in OWNER: continue
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    seen.setdefault(h, p.name)
keep = sorted(seen.values())
print(len(keep), "distinct scored rasters")

X, y, labels = [], [], []
for name in keep:
    with rasterio.open(REG/name) as s:
        a = np.nan_to_num(s.read(1).astype(np.float32), nan=0., posinf=0., neginf=0.)
    a[~fp] = 0.0
    a = np.clip(a, 0., 1.)
    pos = a > 0
    n = int(pos.sum())
    w = a[pos].astype(np.float64); w /= w.sum()
    X.append([float((arrs[nm][pos]*w).sum()) for nm in LAYERS])
    y.append(OWNER[name]); labels.append(name)
X = np.asarray(X); y = np.asarray(y)

rows=[]
rng = np.random.default_rng(0)
for j,nm in enumerate(LAYERS):
    v = X[:,j]; ok=np.isfinite(v)
    rho = float(spearmanr(v[ok], y[ok]).statistic)
    null = np.array([spearmanr(v[ok], rng.permutation(y[ok])).statistic for _ in range(2000)])
    p = float((np.abs(null)>=abs(rho)-1e-12).mean())
    rows.append((nm, rho, p))
rows.sort(key=lambda r:-abs(r[1]))
print(f"\n{'layer':16s} {'rho':>8} {'p_perm':>7}")
for nm,rho,p in rows: print(f"{nm:16s} {rho:+8.3f} {p:7.3f}")

def loo(j):
    v = X[:,j].copy(); v[~np.isfinite(v)] = np.nanmedian(v)
    pred=np.empty(len(y))
    for i in range(len(y)):
        tr=np.ones(len(y),bool); tr[i]=False
        A=np.vstack([v[tr], np.ones(tr.sum())]).T
        c,*_=np.linalg.lstsq(A,y[tr],rcond=None); pred[i]=c[0]*v[i]+c[1]
    return float(np.sqrt(np.mean((pred-y)**2))), pred
base=float(np.sqrt(np.mean((y-y.mean())**2)))
print("baseline LOO RMSE", round(base,5))
for nm,_,_ in rows[:4]:
    r,pred = loo(LAYERS_LIST:=[k for k in LAYERS].index(nm)) if False else loo(list(LAYERS).index(nm))
    print(f"  {nm:16s} LOO RMSE {r:.5f}")
np.save(ROOT/"evidence66/_x.npy", X)
(ROOT/"evidence66/_labels.json").write_text(json.dumps({"keep":keep,"y":[float(v) for v in y],"layers":list(LAYERS)}))

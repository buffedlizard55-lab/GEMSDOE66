#!/usr/bin/env python3
"""Fetch every hash-pinned competition mirror and FAIL CLOSED on any digest mismatch.

Why this exists
---------------
The competition data is login-walled at drivendata.org.  The only reachable copy is the
set of owner-supplied public GitHub blobs pinned by sha256 in ``registry/data_manifest.json``.
Those bytes are NOT organizer-authenticated, so the only thing that makes them usable is the
pin.  A fetch that does not verify is worthless, so this one verifies and exits non-zero on any
mismatch.

Usage
-----
    python3 scripts/fetch_mirrors.py [--manifest registry/data_manifest.json] [--dest data/raw]
                                     [--only id1,id2] [--skip id3]

Requires ``gh`` authenticated for github.com (or GH_TOKEN in the environment).
No DrivenData credentials are used and drivendata.org is never contacted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def gh_blob(repo: str, ref: str, path: str, out: Path, retries: int = 3) -> None:
    """Stream a raw GitHub blob to ``out`` via the contents API."""
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".partial")
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            with tmp.open("wb") as fh:
                subprocess.run(
                    [
                        "gh", "api",
                        f"repos/{repo}/contents/{path}?ref={ref}",
                        "-H", "Accept: application/vnd.github.raw",
                    ],
                    stdout=fh,
                    check=True,
                )
            tmp.replace(out)
            return
        except subprocess.CalledProcessError as exc:  # pragma: no cover - network path
            last_err = exc
            time.sleep(2 ** attempt)
    if tmp.exists():
        tmp.unlink()
    raise RuntimeError(f"failed to fetch {repo}/{path}@{ref}: {last_err}")


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=str(ROOT / "registry" / "data_manifest.json"))
    ap.add_argument("--dest", default=str(ROOT / "data" / "raw"))
    ap.add_argument("--only", default="", help="comma separated ids to fetch")
    ap.add_argument("--skip", default="", help="comma separated ids to skip")
    args = ap.parse_args()

    spec = json.loads(Path(args.manifest).read_text())
    dest = Path(args.dest)
    dest.mkdir(parents=True, exist_ok=True)
    only = {s for s in args.only.split(",") if s}
    skip = {s for s in args.skip.split(",") if s}

    results = []
    failed = []
    for f in spec["files"]:
        fid = f["id"]
        if only and fid not in only:
            continue
        if fid in skip:
            continue
        target = dest / f["dest"]
        # Manifest entries with "repo": null have no reachable mirror (the owner recorded the
        # id and sha256 but never mirrored the bytes).  Report them honestly instead of calling
        # `gh api repos/None/...`, which 404s and aborted the whole restore before the receipt
        # for the 22 reachable files could be written.
        if not f.get("repo"):
            if target.exists():
                got = sha256_of(target)
                ok = got == f["sha256"]
                print(("PASS " if ok else "FAIL ")
                      + f"{fid:34s} {target.stat().st_size:>13,} bytes  {got[:16]}...  (local)")
                results.append({"id": fid, "status": "pass" if ok else "FAIL",
                                "sha256": got, "bytes": target.stat().st_size,
                                "note": "no mirror in manifest; verified against local copy"})
                if not ok:
                    failed.append(fid)
            else:
                print(f"SKIP {fid:34s} {'':>13s} {'':16s}  no mirror repo recorded in manifest")
                results.append({"id": fid, "status": "no_mirror", "sha256": None,
                                "bytes": 0, "note": "manifest has repo: null; not obtainable here"})
            continue
        if target.exists() and target.stat().st_size == f["bytes"]:
            got = sha256_of(target)
            if got == f["sha256"]:
                print(f"CACH {fid:34s} {target.stat().st_size:>13,} bytes  {got[:16]}...")
                results.append({"id": fid, "status": "cached", "sha256": got})
                continue
        t0 = time.time()
        if "parts" in f:
            chunks = []
            for i, p in enumerate(f["parts"]):
                c = dest / f"_part-{fid}-{i:03d}"
                gh_blob(f["repo"], f["ref"], p, c)
                chunks.append(c)
            with target.open("wb") as out:
                for c in chunks:
                    out.write(c.read_bytes())
            for c in chunks:
                c.unlink()
        else:
            gh_blob(f["repo"], f["ref"], f["path"], target)
        got = sha256_of(target)
        nbytes = os.path.getsize(target)
        ok = (got == f["sha256"]) and (nbytes == f["bytes"])
        dt = time.time() - t0
        print(
            ("PASS " if ok else "FAIL ") + f"{fid:34s} {nbytes:>13,} bytes  {got[:16]}...  {dt:5.1f}s",
            flush=True,
        )
        results.append({"id": fid, "status": "pass" if ok else "FAIL", "sha256": got, "bytes": nbytes})
        if not ok:
            failed.append(fid)

    receipt = ROOT / "data" / "restore_receipt.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(
        {"generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "verified": sum(1 for r in results if r["status"] in ("pass", "cached")),
         "cached": sum(1 for r in results if r["status"] == "cached"),
         "no_mirror": [r["id"] for r in results if r["status"] == "no_mirror"],
         "failed": failed,
         "files": results},
        indent=1))
    print(json.dumps({"verified": sum(1 for r in results if r["status"] in ("pass", "cached")),
                      "no_mirror": [r["id"] for r in results if r["status"] == "no_mirror"],
                      "failed": failed}, indent=1))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

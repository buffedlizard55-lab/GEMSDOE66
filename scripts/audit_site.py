#!/usr/bin/env python3
"""Fail-closed documentation/site audit for the current negative run state.

This checks only local documentation links and the published clearance. It is
not a TIFF validator, model evaluator, holdout implementation, or data checker.
"""

from __future__ import annotations

import json
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
CARD_PATH = DOCS / "evidence" / "run-card.json"


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.hrefs.append(href)


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def check_local_links() -> int:
    checked = 0
    for html_path in sorted(DOCS.rglob("*.html")):
        if "_layouts" in html_path.parts:
            continue  # Jekyll templates resolve links from the published site root.
        parser = LinkParser()
        parser.feed(html_path.read_text(encoding="utf-8"))
        for href in parser.hrefs:
            parsed = urlsplit(href)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target_path = unquote(parsed.path)
            target = (html_path.parent / target_path).resolve()
            if not target.exists() and target.suffix.lower() == ".html":
                # GitHub Pages' Jekyll build converts source Markdown into .html.
                markdown_source = target.with_suffix(".md")
                if markdown_source.is_file():
                    target = markdown_source
            if not target.exists():
                fail(f"broken local link in {html_path.relative_to(ROOT)}: {href}")
            checked += 1
    return checked


def main() -> None:
    if not DOCS.is_dir():
        fail("docs/ site directory is missing")
    if not CARD_PATH.is_file():
        fail("negative run card is missing")

    try:
        card = json.loads(CARD_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"run card is not valid JSON: {exc}")

    submission = card.get("submission", {})
    if submission.get("verdict") != "negative":
        fail("this site audit expects a negative run card; update the release gate before changing clearance")
    if submission.get("download_clearance") != "NO" or submission.get("submit_clearance") != "NO":
        fail("negative run card must keep both download and submit clearance at NO")
    if submission.get("file") is not None or submission.get("submission_name") is not None:
        fail("negative run card must not claim a candidate file or submission name")
    if card.get("raster_sha256") is not None or card.get("pixel_sha256") is not None:
        fail("negative run card must not claim raster hashes")
    if card.get("holdout_dti", {}).get("status") != "NOT_RUN":
        fail("holdout status must remain NOT_RUN while the required evaluator/data are absent")
    if card.get("budget", {}).get("experiments_started") != 0:
        fail("the negative run card should report zero experiments")

    for html_path in sorted(DOCS.rglob("*.html")):
        parser = LinkParser()
        parser.feed(html_path.read_text(encoding="utf-8"))
        for href in parser.hrefs:
            suffix = Path(urlsplit(href).path).suffix.lower()
            if suffix in {".tif", ".tiff", ".zip"}:
                fail(f"a negative site must not link a submission artifact: {html_path.relative_to(ROOT)} -> {href}")
    submission_archives = [
        p for p in DOCS.rglob("*")
        if p.is_file() and p.suffix.lower() in {".tif", ".tiff", ".zip"}
    ]
    if submission_archives:
        fail("a negative site must not contain a submission artifact: " + ", ".join(str(p.relative_to(ROOT)) for p in submission_archives))

    index = (DOCS / "index.html").read_text(encoding="utf-8").lower()
    executive = (DOCS / "executive-summary.html").read_text(encoding="utf-8").lower()
    if "do not download or submit a file" not in index:
        fail("home page must clearly state that no file may be downloaded or submitted")
    if "do not submit" not in executive or "no download" not in executive:
        fail("executive summary must clearly state current no-download/no-submit status")
    note = submission.get("note", "")
    if len(note) > 140:
        fail("run-card note exceeds the project limit of 140 characters")

    checked_links = check_local_links()
    print(f"PASS: site links checked={checked_links}; run card is negative; no .tif/.tiff/.zip artifact link is exposed.")
    print("NOTE: this does not validate a submission, evaluate a holdout, or verify external links.")


if __name__ == "__main__":
    main()

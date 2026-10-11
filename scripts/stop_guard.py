"""Fail-closed guard for the stopped channel-steepness experiment lane."""
from __future__ import annotations

import json
from pathlib import Path

_STOP_VERDICTS = {"NEGATIVE-STOP", "NEGATIVE", "INCONCLUSIVE", "STOP", "FAIL"}


def _verdict(record: dict) -> str | None:
    """Read common first-test verdict locations without assuming one schema."""
    summary = record.get("summary")
    if isinstance(summary, dict) and summary.get("verdict") is not None:
        return str(summary["verdict"]).upper()
    if record.get("verdict") is not None:
        return str(record["verdict"]).upper()
    result = record.get("result")
    return str(result).upper() if result is not None else None


def lane_is_stopped(root: Path, runner: str) -> bool:
    """Block lane runners unless status and all recorded first-test evidence permit a run.

    Both the current run's linked first-test file and the historical c7653/H65-1 first tests are
    read. An INCONCLUSIVE result fails the registered PROCEED gate and is therefore a stop, just as
    an explicit NEGATIVE-STOP is. Missing current evidence fails closed.
    """
    status_path = root / "registry" / "current_site_status.json"
    try:
        status = json.loads(status_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"STOP GUARD: {runner} not run — cannot read authoritative lane status ({exc}).")
        return True

    if not isinstance(status, dict):
        print(f"STOP GUARD: {runner} not run — lane status must be an object.")
        return True

    if "channel-steepness" not in status.get("active_lane", ""):
        print(f"STOP GUARD: {runner} not run — channel-steepness is not the registered active lane.")
        return True

    if status.get("status") == "STOP":
        print(f"STOP GUARD: {runner} not run — {status.get('stop_reason', 'lane status is STOP')}.")
        print("No experiment or GeoTIFF was generated. Do not override without separate authorization.")
        return True

    latest = status.get("latest_first_test") or {}
    if not isinstance(latest, dict):
        print(f"STOP GUARD: {runner} not run — latest first test must be an object.")
        return True
    latest_decision = str(latest.get("decision", "")).upper()
    latest_result = str(latest.get("result", "")).upper()
    if "STOP" in latest_decision or latest_result in _STOP_VERDICTS:
        print(f"STOP GUARD: {runner} not run — latest recorded first test is {latest_result or latest_decision}; the PROCEED gate failed.")
        return True

    if latest_result != "PROCEED" or not latest.get("evidence"):
        print(f"STOP GUARD: {runner} not run — affirmative first-test evidence is missing.")
        return True

    paths: list[Path] = []
    latest_evidence = latest.get("evidence")
    if latest_evidence:
        paths.append(root / str(latest_evidence))
    # A negative historical first test remains binding even if a mutable status file is edited.
    paths.extend((root / "evidence" / "e1_lane_test.json", root / "evidence" / "h65_e1_first_test.json"))
    seen: set[Path] = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        try:
            record = json.loads(path.read_text())
        except FileNotFoundError:
            if latest_evidence and path == root / str(latest_evidence):
                print(f"STOP GUARD: {runner} not run — cannot verify latest first-test evidence ({path}).")
                return True
            continue
        except (OSError, json.JSONDecodeError) as exc:
            if latest_evidence and path == root / str(latest_evidence):
                print(f"STOP GUARD: {runner} not run — latest first-test evidence is unreadable ({exc}).")
                return True
            # Historical evidence is also a fail-closed input: corruption must not silently permit a run.
            print(f"STOP GUARD: {runner} not run — recorded first-test evidence is unreadable ({path}: {exc}).")
            return True

        if not isinstance(record, dict):
            print(f"STOP GUARD: {runner} not run — first-test evidence must be an object.")
            return True
        verdict = _verdict(record)
        if latest_evidence and path == root / str(latest_evidence) and verdict != "PROCEED":
            print(f"STOP GUARD: {runner} not run — latest evidence is {verdict}, not PROCEED; STOP applies.")
            return True
        if verdict in _STOP_VERDICTS:
            detail = "INCONCLUSIVE fails the preregistered PROCEED gate" if verdict == "INCONCLUSIVE" else f"recorded verdict is {verdict}"
            print(f"STOP GUARD: {runner} not run — {path.relative_to(root)}: {detail}; STOP applies.")
            return True

    if status.get("status") not in {"ACTIVE", "AUTHORIZED"}:
        print(f"STOP GUARD: {runner} not run — lane status {status.get('status')!r} is not ACTIVE/AUTHORIZED.")
        return True

    return False

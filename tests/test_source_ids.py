import json
import re
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "docs" / "data"


def test_claim_and_hypothesis_citations_resolve_to_source_register():
    source_data = json.loads((DATA / "sources.json").read_text(encoding="utf-8"))
    registered = {entry["id"] for entry in source_data["sources"]}
    for name in ("claims.json", "hypotheses.json", "irregularities.json"):
        payload = json.loads((DATA / name).read_text(encoding="utf-8"))
        cited = set(re.findall(r"\bS\d{2}\b", json.dumps(payload, ensure_ascii=False)))
        assert cited <= registered, f"{name} cites unregistered source IDs: {sorted(cited - registered)}"

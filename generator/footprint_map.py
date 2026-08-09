"""Loads mapping/footprint_map.yaml (plan §3.2, Route A) into a lookup
keyed the same way autoLibrarySymbols.py builds its footprints_lookup miss
key: f"{ref_designator}_{pkg_case}". Only confidence-A matches belong here
-- an unresolved symbol (falls through to the ES: placeholder, caught by
library_checks.check_footprints) is safer than a wrong footprint (plan §3.5).
"""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MAP_PATH = ROOT / "mapping" / "footprint_map.yaml"


def load_footprint_map(path: Path = DEFAULT_MAP_PATH) -> dict[str, str]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    lookup: dict[str, str] = {}
    for rule in data.get("rules", []):
        match = rule["match"]
        key = f"{match['ref']}_{match['pkg_case']}"
        lookup[key] = rule["footprint"]
    return lookup

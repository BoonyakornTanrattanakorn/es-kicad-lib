from pathlib import Path

from generator.footprint_map import DEFAULT_MAP_PATH, load_footprint_map


def test_default_map_loads():
    lookup = load_footprint_map()
    assert len(lookup) > 0


def test_resistor_0402_resolves_to_stock_lib_id():
    lookup = load_footprint_map()
    assert lookup["R_0402 (1005)"] == "Resistor_SMD:R_0402_1005Metric"


def test_capacitor_0805_resolves_to_stock_lib_id():
    lookup = load_footprint_map()
    assert lookup["C_0805 (2012)"] == "Capacitor_SMD:C_0805_2012Metric"


def test_unmapped_key_absent():
    lookup = load_footprint_map()
    assert "R_4527" not in lookup


def test_custom_map_path(tmp_path):
    custom = tmp_path / "custom.yaml"
    custom.write_text(
        'rules:\n  - match: {pkg_case: "TEST-1", ref: X}\n    footprint: "TestLib:TEST-1"\n',
        encoding="utf-8",
    )
    lookup = load_footprint_map(custom)
    assert lookup == {"X_TEST-1": "TestLib:TEST-1"}


def test_map_file_exists_at_default_path():
    assert DEFAULT_MAP_PATH.exists()

from pathlib import Path

from generator.library_writer import filter_resolved_symbols, generate_kicad_symbol_libs


def _sym(footprint: str) -> str:
    return f'\t(symbol "test"\n\t\t(property "Footprint" "{footprint}"\n\t\t\t(at 0 0 0)\n\t\t)\n\t)\n'


def test_filter_resolved_symbols_drops_unresolved_placeholders():
    symbols = [
        _sym("Resistor_SMD:R_0402_1005Metric"),
        _sym("ES:R_4527"),
        _sym("Diode_SMD:D_SMA"),
        _sym("ES:C_RADIAL"),
    ]
    kept, dropped = filter_resolved_symbols(symbols)

    assert len(kept) == 2
    assert dropped == 2
    assert "Resistor_SMD:R_0402_1005Metric" in kept[0]
    assert "Diode_SMD:D_SMA" in kept[1]


def test_filter_resolved_symbols_keeps_everything_when_all_resolved():
    symbols = [_sym("Resistor_SMD:R_0402_1005Metric"), _sym("Diode_SMD:D_SMA")]
    kept, dropped = filter_resolved_symbols(symbols)
    assert len(kept) == 2
    assert dropped == 0


def test_filter_resolved_symbols_drops_everything_when_all_unresolved():
    symbols = [_sym("ES:R_4527"), _sym("ES:C_RADIAL")]
    kept, dropped = filter_resolved_symbols(symbols)
    assert kept == []
    assert dropped == 2


def test_filter_resolved_symbols_empty_input():
    kept, dropped = filter_resolved_symbols([])
    assert kept == []
    assert dropped == 0


def test_generate_kicad_symbol_libs_skips_empty_lists(tmp_path):
    symbols = {"Resistors": [_sym("Resistor_SMD:R_0402_1005Metric")], "Inductors": []}
    generate_kicad_symbol_libs(symbols, tmp_path)

    assert (tmp_path / "ES-Resistors.kicad_sym").exists()
    assert not (tmp_path / "ES-Inductors.kicad_sym").exists()


def test_generate_kicad_symbol_libs_writes_expected_files(tmp_path):
    symbols = {"Resistors": [_sym("Resistor_SMD:R_0402_1005Metric")]}
    generate_kicad_symbol_libs(symbols, tmp_path)

    out_file = tmp_path / "ES-Resistors.kicad_sym"
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    assert content.startswith("(kicad_symbol_lib")
    assert "Resistor_SMD:R_0402_1005Metric" in content

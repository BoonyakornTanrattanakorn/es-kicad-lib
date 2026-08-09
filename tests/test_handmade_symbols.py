import shutil
from pathlib import Path

import pytest

from generator.handmade_symbols import update_component_inplace, update_library_stock_inplace

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_ES_PN = "0102-0295-5"  # present in ES-Resistors.kicad_sym fixture


@pytest.fixture
def symbols_dir(tmp_path):
    d = tmp_path / "symbols"
    d.mkdir()
    shutil.copy(FIXTURES / "ES-Resistors.kicad_sym", d / "ES-Resistors.kicad_sym")
    return d


@pytest.fixture
def archived_dir(tmp_path):
    d = tmp_path / "Archived-Symbols"
    d.mkdir()
    return d


def test_update_component_inplace_patches_stock_and_price(symbols_dir, archived_dir):
    ok = update_component_inplace(
        SAMPLE_ES_PN,
        symbols_dir,
        archived_dir,
        "Resistors",
        {"stock": "9999", "price": "1.234THB"},
    )
    assert ok is True

    content = (symbols_dir / "ES-Resistors.kicad_sym").read_text(encoding="utf-8")
    assert f'(property "ES_PN" "{SAMPLE_ES_PN}"' in content
    assert '(property "Stock" "9999"' in content
    assert '(property "Price" "1.234THB"' in content


def test_update_component_inplace_unknown_es_pn_returns_false(symbols_dir, archived_dir):
    ok = update_component_inplace(
        "9999-9999-9",
        symbols_dir,
        archived_dir,
        "Resistors",
        {"stock": "1"},
    )
    assert ok is False


def test_update_component_inplace_preserves_other_symbols(symbols_dir, archived_dir):
    before = (symbols_dir / "ES-Resistors.kicad_sym").read_text(encoding="utf-8")
    symbol_count_before = before.count('(symbol "')

    update_component_inplace(SAMPLE_ES_PN, symbols_dir, archived_dir, "Resistors", {"stock": "42"})

    after = (symbols_dir / "ES-Resistors.kicad_sym").read_text(encoding="utf-8")
    assert after.count('(symbol "') == symbol_count_before


def test_update_library_stock_inplace_zeroes_and_archives_missing_parts(symbols_dir, archived_dir):
    # Every ES_PN except our sample is treated as no-longer-in-stock.
    update_library_stock_inplace(
        "Resistors",
        symbols_dir,
        archived_dir,
        in_stock_es_pns={SAMPLE_ES_PN},
    )

    content = (symbols_dir / "ES-Resistors.kicad_sym").read_text(encoding="utf-8")
    assert f'(property "ES_PN" "{SAMPLE_ES_PN}"' in content

    archived_files = list(archived_dir.glob("*.kicad_sym"))
    assert len(archived_files) > 0
    # Archived files shouldn't include the still-in-stock sample.
    assert not any(f.stem == SAMPLE_ES_PN for f in archived_files)


def test_update_library_stock_inplace_archived_symbol_is_valid_fragment(symbols_dir, archived_dir):
    update_library_stock_inplace("Resistors", symbols_dir, archived_dir, in_stock_es_pns={SAMPLE_ES_PN})

    archived_files = list(archived_dir.glob("*.kicad_sym"))
    sample_archive = archived_files[0].read_text(encoding="utf-8")
    assert sample_archive.startswith("(kicad_symbol_lib")
    assert sample_archive.rstrip().endswith(")")
    assert '(property "ES_PN"' in sample_archive

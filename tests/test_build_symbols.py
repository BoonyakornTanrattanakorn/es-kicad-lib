from pathlib import Path

from generator.build_symbols import build_all_symbols

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_DB = FIXTURES / "es-parts-sample.sqlite"


def test_build_all_symbols_produces_expected_libraries():
    symbols_by_lib = build_all_symbols(SAMPLE_DB)

    assert set(symbols_by_lib.keys()) == {"Resistors", "Capacitors", "Diodes"}
    assert len(symbols_by_lib["Resistors"]) > 0
    assert len(symbols_by_lib["Capacitors"]) > 0
    assert len(symbols_by_lib["Diodes"]) > 0


def test_resistor_symbols_carry_es_schema_properties():
    symbols_by_lib = build_all_symbols(SAMPLE_DB)
    sym = symbols_by_lib["Resistors"][0]

    assert '(property "ES_PN"' in sym
    assert '(property "ES_URL"' in sym
    assert '(property "Stock_Ratchaphruek"' in sym
    assert '(property "Stock_BanMo"' in sym
    assert '(property "Stock_Date"' in sym
    assert '(property "LCSC"' not in sym
    assert '(property "Process"' not in sym


def test_symbol_names_are_deduplicated():
    symbols_by_lib = build_all_symbols(SAMPLE_DB)
    names = []
    for symbols in symbols_by_lib.values():
        for sym in symbols:
            start = sym.index('(symbol "') + len('(symbol "')
            end = sym.index('"', start)
            names.append(sym[start:end])
    assert len(names) == len(set(names)), "duplicate symbol names across generated libraries"


def test_most_symbols_resolve_to_route_a_stock_footprints():
    import re

    symbols_by_lib = build_all_symbols(SAMPLE_DB)
    all_footprints = []
    for symbols in symbols_by_lib.values():
        for sym in symbols:
            m = re.search(r'\(property "Footprint" "([^"]+)"', sym)
            assert m is not None
            all_footprints.append(m.group(1))

    resolved = [fp for fp in all_footprints if not fp.startswith("ES:")]
    unresolved = [fp for fp in all_footprints if fp.startswith("ES:")]

    assert len(resolved) > 0
    assert all(":" in fp for fp in resolved), "resolved footprints must be LIB_ID (library:name)"
    # R_4527 (large power resistor) has no clean KiCad stock equivalent and
    # should correctly fall through to the ES: placeholder rather than
    # guess wrong, per plan §3.5's confidence policy.
    assert "ES:R_4527" in unresolved


def test_footprint_map_file_used_by_default():
    # Passing a nonexistent map path should leave everything unresolved,
    # proving the default map (not luck) is what makes resolution work.
    symbols_by_lib = build_all_symbols(SAMPLE_DB, footprint_map_path=Path("/nonexistent/map.yaml"))
    sym = symbols_by_lib["Resistors"][0]
    assert '(property "Footprint" "ES:' in sym


def test_dedup_suffix_is_unbounded_past_six_collisions():
    # Regression test: CDFER's original ",(2)".."(6)" ladder silently fell
    # through to a colliding name past 6 duplicates, which made every
    # symbol past the 6th unreachable in KiCad (its parser keeps only the
    # last symbol with a given name on collision). Caught 2026-08-09 when
    # a full-catalogue run hit 379 collisions in Capacitors alone -- the
    # 73-part sample fixture never had more than 6 dupes of one name, so
    # this needs its own test rather than relying on sample data.
    from generator.autoLibrarySymbols import generate_kicad_symbol

    names_lookup = []
    names = []
    for i in range(10):
        sym = generate_kicad_symbol(
            mode="Resistors", secondary_mode=None, es_pn=f"0000-000{i}-0", es_url="",
            datasheet="", description="", footprint="0402", value="10K", keywords="",
            price="", min_order_qty="", stock="1", stock_ratchaphruek="1", stock_banmo="0",
            stock_date="2026-08-09", category="", manufacturer="", manufacturerPartID=f"MPN{i}",
            attributes={}, units=1, footprints_lookup={}, names_lookup=names_lookup,
        )
        start = sym.index('(symbol "') + len('(symbol "')
        end = sym.index('"', start)
        names.append(sym[start:end])

    assert len(names) == len(set(names)), f"collision past the old ,(6) cap: {names}"
    assert "0402,10K,(9)" in names or "0402,10K,(10)" in names

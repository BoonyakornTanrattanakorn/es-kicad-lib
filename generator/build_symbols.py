"""Drives T1 auto-generated symbol creation (plan §2.1-2.3): reads
es-parts.sqlite, dispatches each row to a mode/value via catc_modes.py +
value_extraction.py, calls generate_kicad_symbol, and writes one
symbols/ES-{lib_name}.kicad_sym per lib_name via generate_kicad_symbol_libs.

This is the ES-native replacement for libraryCreatorScript.py's main driver
loop. Dropped relative to CDFER: joint-cost pricing math (ES is a
distributor with list pricing, not a fab with assembly service pricing) and
basic/preferred/extended tiering (no ES equivalent) — see PORTING.md.
"""
import json
import sqlite3
from pathlib import Path
from typing import Optional

from generator.autoLibrarySymbols import generate_kicad_symbol
from generator.catc_modes import lookup_mode
from generator.footprint_map import DEFAULT_MAP_PATH, load_footprint_map
from generator.value_extraction import (
    extract_capacitor_value,
    extract_capacitor_voltage,
    extract_diode_secondary_mode,
    extract_diode_value,
    extract_inductor_secondary_mode_and_value,
    extract_led_value_and_color,
    extract_resistance_value,
    extract_transistor_secondary_mode,
    extract_transistor_value,
    extract_variable_resistor_secondary_mode_and_value,
)

ROOT = Path(__file__).resolve().parent.parent

# catc -> lib_name, i.e. which symbols/ES-{lib_name}.kicad_sym a part lands in.
LIB_NAME_BY_MODE = {
    "Resistors": "Resistors",
    "Capacitors": "Capacitors",
    "Diodes": "Diodes",
    "Inductors": "Inductors",
    "Transistors": "Transistors",
    "Variable-Resistors": "Variable-Resistors",
}


def _latest_stock(conn: sqlite3.Connection, es_pn: str) -> dict[str, int]:
    rows = conn.execute(
        """
        SELECT warehouse, qty FROM stock
        WHERE es_pn = ? AND scraped_at = (SELECT MAX(scraped_at) FROM stock WHERE es_pn = ?)
        """,
        (es_pn, es_pn),
    ).fetchall()
    return {w: q for w, q in rows}


def _latest_unit_price(conn: sqlite3.Connection, es_pn: str) -> str:
    row = conn.execute(
        "SELECT unit_price, currency FROM price WHERE es_pn = ? ORDER BY min_qty ASC LIMIT 1",
        (es_pn,),
    ).fetchone()
    if row is None:
        return ""
    price, currency = row
    return f"{price:.3f}{currency}"


def build_row(conn: sqlite3.Connection, row: sqlite3.Row, names_lookup: list, footprints_lookup: dict) -> Optional[tuple[str, str]]:
    """Returns (lib_name, symbol_sexpr) or None if the row's catc isn't a T1 mode."""
    catc = row["catc"]
    dispatch = lookup_mode(catc)
    if dispatch is None:
        return None
    mode, secondary_mode = dispatch

    specs = json.loads(row["specs_json"] or "{}")

    if mode == "Resistors":
        value = extract_resistance_value(specs)
    elif mode == "Capacitors":
        value = extract_capacitor_value(specs)
        voltage = extract_capacitor_voltage(specs)
        if voltage:
            specs = {**specs, "Voltage Rated": voltage}
    elif mode == "Diodes":
        mfr_package = row["pkg_mfr"]
        secondary_mode = extract_diode_secondary_mode(specs, secondary_mode, mfr_package)
        if secondary_mode == "LED" or secondary_mode == "LED-Bi-Colour":
            value, secondary_mode = extract_led_value_and_color(specs)
        else:
            value = extract_diode_value(specs, secondary_mode)
    elif mode == "Transistors":
        secondary_mode = extract_transistor_secondary_mode(catc, specs)
        value = extract_transistor_value(specs)
    elif mode == "Inductors":
        secondary_mode, value = extract_inductor_secondary_mode_and_value(catc, specs)
    elif mode == "Variable-Resistors":
        secondary_mode, value = extract_variable_resistor_secondary_mode_and_value(catc, specs)
    else:
        value = "?"

    stock_by_wh = _latest_stock(conn, row["es_pn"])
    stock_ratchaphruek = next((v for k, v in stock_by_wh.items() if "Rachapreuk" in k or "Ratchaphruek" in k), 0)
    stock_banmo = next((v for k, v in stock_by_wh.items() if "Banmoh" in k or "Ban Mo" in k), 0)
    total_stock = sum(stock_by_wh.values())

    footprint_token = row["pkg_case"] or row["pkg_mfr"] or "Unknown"

    symbol = generate_kicad_symbol(
        mode=mode,
        secondary_mode=secondary_mode,
        es_pn=row["es_pn"],
        es_url=f"https://www.es.co.th/detail.asp?Prod={row['es_pn'].replace('-', '')}",
        datasheet=row["datasheet_url"] or "",
        description=row["description"] or "",
        footprint=footprint_token,
        value=value,
        keywords="",
        price=_latest_unit_price(conn, row["es_pn"]),
        min_order_qty="",
        stock=str(total_stock),
        stock_ratchaphruek=str(stock_ratchaphruek),
        stock_banmo=str(stock_banmo),
        stock_date=row["last_seen"][:10] if row["last_seen"] else "",
        category=row["category_path"] or "",
        manufacturer=row["mfr"] or "",
        manufacturerPartID=row["mpn"] or "",
        attributes={k: v for k, v in specs.items() if k not in (
            "Datasheet", "Product Brochure", "Application Note", "Product Category",
            "Family", "Product Part No.", "ES Part No.", "Manufacturer",
            "Package/Case", "Mfr Package", "Packaging", "Qty/Packaging",
            "Mfr_Std_pack", "ES_Std_pack", "Unit", "Weight (Gram)",
            "Warranty (year)", "PB-Free", "RoHS", "Mounting Type",
        ) and v and v != "-"},
        units=1,
        footprints_lookup=footprints_lookup,
        names_lookup=names_lookup,
    )

    lib_name = LIB_NAME_BY_MODE[mode]
    return lib_name, symbol


def build_all_symbols(db_path: Path, footprint_map_path: Path = DEFAULT_MAP_PATH) -> dict[str, list[str]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    symbols_by_lib: dict[str, list[str]] = {}
    names_lookup: list[str] = []
    footprints_lookup: dict[str, str] = load_footprint_map(footprint_map_path) if footprint_map_path.exists() else {}

    for row in conn.execute("SELECT * FROM parts"):
        result = build_row(conn, row, names_lookup, footprints_lookup)
        if result is None:
            continue
        lib_name, symbol = result
        symbols_by_lib.setdefault(lib_name, []).append(symbol)

    conn.close()
    return symbols_by_lib


if __name__ == "__main__":
    import argparse

    from generator.library_writer import filter_resolved_symbols, generate_kicad_symbol_libs

    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=ROOT.parent / "es-parts-database" / "out" / "es-parts.sqlite")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "symbols")
    parser.add_argument(
        "--filter-unresolved",
        action="store_true",
        help="drop symbols whose Footprint is still an ES: placeholder (plan §3.5 Tier C) before writing -- "
        "use for a shippable/packageable library; omit to keep the full 1:1 view of the database for inspection",
    )
    args = parser.parse_args()

    symbols_by_lib = build_all_symbols(args.db)

    if args.filter_unresolved:
        total_dropped = 0
        for lib_name in list(symbols_by_lib):
            kept, dropped = filter_resolved_symbols(symbols_by_lib[lib_name])
            symbols_by_lib[lib_name] = kept
            total_dropped += dropped
        print(f"dropped {total_dropped} symbols with unresolved footprints")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    generate_kicad_symbol_libs(symbols_by_lib, args.out_dir)

    for lib_name, symbols in symbols_by_lib.items():
        print(f"{lib_name}: {len(symbols)} symbols")

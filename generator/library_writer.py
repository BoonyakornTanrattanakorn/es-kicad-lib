# Adapted from CDFER/JLCPCB-Kicad-Library's libraryCreatorScript.py
# generate_kicad_symbol_libs() (MIT licensed, Copyright (c) 2023 Chris).
# See PORTING.md. Only the filename prefix (JLCPCB- -> ES-) and output
# directory parameter changed; the s-expression wrapper is unchanged.
import re
from pathlib import Path


def generate_kicad_symbol_libs(symbols: dict[str, list[str]], out_dir: Path) -> None:
    for lib_name, symbol_list in symbols.items():
        if not symbol_list:
            continue  # nothing resolved for this mode yet -- skip rather than ship an empty library

        lib_content = "(kicad_symbol_lib\n"
        lib_content += "\t(version 20231120)\n"
        lib_content += '\t(generator "es-kicad-lib")\n'
        lib_content += '\t(generator_version "8.0")\n'
        for symbol in symbol_list:
            lib_content += symbol + "\n"
        lib_content += ")\n"

        lib_content = lib_content.replace("℃", "°C")

        library_filename = out_dir / f"ES-{lib_name}.kicad_sym"
        library_filename.write_text(lib_content, encoding="utf-8")


def filter_resolved_symbols(symbols: list[str]) -> tuple[list[str], int]:
    """Drops any symbol whose Footprint property is still an unresolved
    ES:{name} placeholder (plan §3.5, Tier C: "excluded from the library").
    build_all_symbols() deliberately keeps unresolved symbols in its output
    (useful for library_checks.check_footprints() and dev inspection) -- this
    is the filter that runs right before packaging, so nothing unplaceable
    ships. Returns (kept, dropped_count).
    """
    kept = []
    dropped = 0
    for sym in symbols:
        m = re.search(r'\(property "Footprint" "([^"]+)"', sym)
        if m and m.group(1).startswith("ES:"):
            dropped += 1
            continue
        kept.append(sym)
    return kept, dropped

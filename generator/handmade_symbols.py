"""Update-in-place for T2 hand-drawn symbols (plan §2.1, "Update-in-place
for handmade symbols"): patches only the volatile property values inside a
committed .kicad_sym file, leaving the hand-drawn geometry untouched.

Adapted from CDFER/JLCPCB-Kicad-Library's handmadeLibrarySymbols.py (MIT
licensed, Copyright (c) 2023 Chris). See PORTING.md: same line-walking
approach, but keyed on ES_PN instead of LCSC, and paths are passed in
rather than hardcoded relative to the CWD so this is testable in isolation.
"""
import os
import re
from pathlib import Path


def generate_property(property: str, value: str) -> str:
    return f'\t\t(property "{property}" "{value}"\n\t\t\t(at 0 0 0)\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t)\n\t\t\t\t(hide yes)\n\t\t\t)\n\t\t)\n'


def update_component_inplace(
    es_pn: str,
    symbols_dir: Path,
    archived_symbols_dir: Path,
    library_name: str,
    properties: dict,
) -> bool:
    filename = symbols_dir / f"ES-{library_name}.kicad_sym"
    with filename.open("r", encoding="utf-8") as file:
        lines = file.readlines()

    es_pn_found = False
    properties_found = {prop: False for prop in properties.keys()}
    keywords_index = None

    for i, line in enumerate(lines):
        if not es_pn_found:
            if f'(property "ES_PN" "{es_pn}"' in line:
                es_pn_found = True
                line_offset = 1
                # Work upwards to find datasheet/description, which sit
                # above ES_PN in the property block generate_kicad_symbol
                # writes (see autoLibrarySymbols.py's fixed property order).
                if "datasheet" in properties or "description" in properties:
                    while ("(symbol" not in lines[i - line_offset]) and (line_offset < 30):
                        if '(property "Datasheet"' in lines[i - line_offset] and "datasheet" in properties:
                            lines[i - line_offset] = f'\t\t(property "Datasheet" "{properties["datasheet"]}"\n'
                            properties_found["datasheet"] = True
                        elif '(property "Description"' in lines[i - line_offset] and "description" in properties:
                            lines[i - line_offset] = f'\t\t(property "Description" "{properties["description"]}"\n'
                            properties_found["description"] = True
                        line_offset += 1
        else:
            if '(property "ki_keywords"' in line:
                keywords_index = i
            elif "(property " in line:
                for prop, found in properties_found.items():
                    if f'(property "{prop.title()}"' in line:
                        if not found and prop not in ("datasheet", "description"):
                            lines[i] = f'\t\t(property "{prop.title()}" "{properties[prop]}"\n'
                            properties_found[prop] = True
            elif "(symbol" in line:
                for prop, found in properties_found.items():
                    if not found and prop not in ("datasheet", "description") and keywords_index is not None:
                        lines.insert(keywords_index, generate_property(prop.title(), properties[prop]))
                break

    if not es_pn_found:
        archived_es_pns = [
            os.path.splitext(f)[0] for f in os.listdir(archived_symbols_dir) if f.endswith(".kicad_sym")
        ]
        if es_pn in archived_es_pns:
            print(
                f"Error: {es_pn} Stock={properties.get('stock')} not found in library {filename} but it was found in the archive"
            )
        else:
            print(f"Error: {es_pn} Stock={properties.get('stock')} not found in library {filename}")
        return False

    with filename.open("w", encoding="utf-8") as file:
        file.writelines(lines)
    return True


SYMBOL_HEADER_LINES = """(kicad_symbol_lib
    (version 20231120)
    (generator "es-kicad-lib_Archive_Tool")
    (generator_version "0.0")
 """

SYMBOL_FOOTER_LINES = """)
"""


def create_archived_symbol_file(
    symbol_start_line: int, symbol_end_line: int, lines: list[str], es_pn: str, archived_symbols_dir: Path
) -> None:
    archived_symbol_lines = lines[symbol_start_line:symbol_end_line]
    archived_filename = archived_symbols_dir / f"{es_pn}.kicad_sym"
    with archived_filename.open("w", encoding="utf-8") as archived_file:
        archived_file.write(SYMBOL_HEADER_LINES)
        archived_file.writelines(archived_symbol_lines)
        archived_file.write(SYMBOL_FOOTER_LINES)
    print(f"Archived symbol as: {archived_filename}")


def update_library_stock_inplace(
    library_name: str,
    symbols_dir: Path,
    archived_symbols_dir: Path,
    in_stock_es_pns: set[str],
) -> None:
    """in_stock_es_pns: ES P/Ns present in the latest published catalogue
    (es-components.csv). Anything with a symbol in this library but absent
    from that set gets its Stock zeroed and, once it hits zero, archived —
    same behavior as CDFER's CSV-membership check, against ES_PN instead of
    lcsc, and against an in-memory set instead of re-reading a CSV per call.
    """
    filename = symbols_dir / f"ES-{library_name}.kicad_sym"
    with filename.open("r", encoding="utf-8") as file:
        lines = file.readlines()

    no_stock = False
    es_pn = None
    symbol_start_line = 0

    for i, line in enumerate(lines):
        lines[i] = lines[i].replace("℃", "°C")
        if line.startswith("\t(") or line.startswith(")"):
            if no_stock:
                create_archived_symbol_file(symbol_start_line, i, lines, es_pn, archived_symbols_dir)
                lines[symbol_start_line:i] = [""] * (i - symbol_start_line)
                no_stock = False
            symbol_start_line = i

        elif '(property "ES_PN" "' in line:
            m = re.search(r'\(property "ES_PN" "([^"]+)"', line)
            es_pn = m.group(1) if m else None
            if es_pn is not None and es_pn not in in_stock_es_pns:
                no_stock = True
                print(f"Error: No stock found for ES_PN {es_pn}")

        elif '(property "Stock"' in line and no_stock:
            lines[i] = '\t\t(property "Stock" "0"\n'

    with filename.open("w", encoding="utf-8") as file:
        file.writelines(lines)

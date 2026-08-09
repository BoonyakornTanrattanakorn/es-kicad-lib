"""One-shot tool: ports CDFER hand-drawn symbol geometry + Route B
footprints for the curated reuse table (mapping/cdfer_reuse.yaml) into ES
symbols, re-pointed at matching ES rows via es-parts-database's detail.asp
data. Not part of the nightly pipeline -- run manually when extending
cdfer_reuse.yaml with new matched parts.

Why this is safe to reuse: a part's pinout doesn't change because a
different distributor sells it. The symbol's pin names/numbers/positions
and the SOIC/SOP footprint's pad geometry are physical facts about the
package, not JLCPCB-specific data -- only the sourcing properties (ES_PN,
price, stock, description, ...) are replaced. See PORTING.md and
mapping/cdfer_reuse.yaml's header comment for the full rationale and the
match verification process (every es_pn was confirmed live against
es.co.th with a package-compatible variant before being added).

Requires a local clone of https://github.com/CDFER/JLCPCB-Kicad-Library
(MIT licensed) -- pass its path via --cdfer-repo.

Usage:
    python -m generator.port_cdfer_reuse --cdfer-repo /path/to/JLCPCB-Kicad-Library
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

REUSE_TABLE_PATH = ROOT / "mapping" / "cdfer_reuse.yaml"

CDFER_SYMBOL_FILES = [
    "JLCPCB-Analog.kicad_sym",
    "JLCPCB-ICs.kicad_sym",
    "JLCPCB-Interface.kicad_sym",
    "JLCPCB-MCUs.kicad_sym",
    "JLCPCB-Memory.kicad_sym",
]

CATEGORY_BY_CDFER_FILE = {
    "JLCPCB-Analog.kicad_sym": "Analog",
    "JLCPCB-ICs.kicad_sym": "Analog",
    "JLCPCB-Interface.kicad_sym": "Interface_Reused",
    "JLCPCB-MCUs.kicad_sym": "MCUs_Reused",
    "JLCPCB-Memory.kicad_sym": "Memory_Reused",
}


def load_cdfer_symbol_block(cdfer_repo: Path, symbol_name: str) -> tuple[str, str]:
    """Returns (block_text, source_filename)."""
    for filename in CDFER_SYMBOL_FILES:
        path = cdfer_repo / "symbols" / filename
        content = path.read_text(encoding="utf-8")
        marker = f'\t(symbol "{symbol_name}"'
        i = content.find(marker)
        if i == -1:
            continue
        j = content.find('\n\t(symbol "', i + 10)
        if j == -1:
            j = content.rfind("\n)")
        return content[i:j], filename
    raise KeyError(f"{symbol_name!r} not found in any CDFER symbol library")


def extract_geometry_subsymbols(block: str, old_name: str, new_name: str) -> str:
    """Returns every (symbol "{old_name}_N_1" ...) sub-block -- pins, shapes
    -- geometry byte-for-byte unchanged, with only the name swapped."""
    parts = []
    for m in re.finditer(re.escape(f'(symbol "{old_name}_') + r'(\d+_\d+)"', block):
        start = m.start()
        depth = 0
        end = start
        for i in range(start, len(block)):
            if block[i] == "(":
                depth += 1
            elif block[i] == ")":
                depth -= 1
                if depth == 0:
                    end = i
                    break
        sub = block[start : end + 1]
        suffix = m.group(1)
        sub = sub.replace(f'"{old_name}_{suffix}"', f'"{new_name}_{suffix}"', 1)
        parts.append(sub)
    return "\n\t\t".join(parts)


def build_es_symbol(new_name: str, geometry: str, es_pn: str, mpn: str, manufacturer: str,
                     datasheet_url: str, description: str, stock_total: str,
                     stock_ratchaphruek: str, stock_banmo: str, stock_date: str,
                     price: str, min_order_qty: str, footprint_lib_id: str) -> str:
    def prop(key, value, at="0 0 0", hide=True):
        hide_str = "\n\t\t\t\t(hide yes)" if hide else ""
        return f'\t\t(property "{key}" "{value}"\n\t\t\t(at {at})\n\t\t\t(effects\n\t\t\t\t(font\n\t\t\t\t\t(size 1.27 1.27)\n\t\t\t\t){hide_str}\n\t\t\t)\n\t\t)\n'

    header = f'\t(symbol "{new_name}"\n\t\t(pin_numbers hide)\n\t\t(pin_names\n\t\t\t(offset 0)\n\t\t)\n'
    header += "\t\t(exclude_from_sim no)\n\t\t(in_bom yes)\n\t\t(on_board yes)\n"

    props = prop("Reference", "U", hide=False)
    props += prop("Value", mpn, hide=False)
    props += prop("Footprint", footprint_lib_id)
    props += prop("Datasheet", datasheet_url or "")
    props += prop("Description", description or "")
    props += prop("ES_PN", es_pn)
    props += prop("ES_URL", f"https://www.es.co.th/detail.asp?Prod={es_pn.replace('-', '')}")
    props += prop("Stock", stock_total)
    props += prop("Stock_Ratchaphruek", stock_ratchaphruek)
    props += prop("Stock_BanMo", stock_banmo)
    props += prop("Stock_Date", stock_date)
    props += prop("Price", price)
    props += prop("Min Order Qty", min_order_qty)
    props += prop("Manufacturer", manufacturer)
    props += prop("Part", mpn)
    props += prop("ki_fp_filters", "U_*")

    return header + props + "\t\t" + geometry + "\n\t)\n"


def port(cdfer_repo: Path, es_session, parse_detail_html, out_dir: Path, stock_date: str) -> dict:
    reuse = yaml.safe_load(REUSE_TABLE_PATH.read_text(encoding="utf-8"))
    symbols_by_category: dict[str, list[str]] = {}
    footprints_copied: set[str] = set()
    footprints_dst = out_dir / "footprints" / "ES.pretty"

    for entry in reuse["parts"]:
        cdfer_name = entry["cdfer_symbol"]
        cdfer_fp = entry["cdfer_footprint"]
        variants = entry.get("variants") or []
        if not variants:
            continue

        try:
            block, src_file = load_cdfer_symbol_block(cdfer_repo, cdfer_name)
        except KeyError as exc:
            print(f"MISSING SOURCE: {exc}")
            continue
        category = CATEGORY_BY_CDFER_FILE.get(src_file, "Analog")

        for variant in variants:
            es_pn = variant["es_pn"]
            resp = es_session.get("detail.asp", params={"Prod": es_pn.replace("-", "")})
            detail = parse_detail_html(resp.text)
            if detail is None:
                print(f"  no detail page for {es_pn}, skipping")
                continue

            new_symbol_name = detail.mpn
            geometry = extract_geometry_subsymbols(block, cdfer_name, new_symbol_name)

            if variant["footprint_source"] == "cdfer":
                footprint_lib_id = f"ES:{cdfer_fp}"
                src_mod = cdfer_repo / "footprints" / "JLCPCB.pretty" / f"{cdfer_fp}.kicad_mod"
                if src_mod.exists() and cdfer_fp not in footprints_copied:
                    footprints_dst.mkdir(parents=True, exist_ok=True)
                    shutil.copy(src_mod, footprints_dst / f"{cdfer_fp}.kicad_mod")
                    footprints_copied.add(cdfer_fp)
            else:
                footprint_lib_id = variant["footprint"]

            rw = {w.warehouse: w.qty for w in detail.stock_by_warehouse}
            ratchaphruek = next((v for k, v in rw.items() if "Rachapreuk" in k or "Ratchaphruek" in k), 0)
            banmo = next((v for k, v in rw.items() if "Banmoh" in k or "Ban Mo" in k), 0)
            price = f"{detail.price_breaks[0].unit_price}THB" if detail.price_breaks else ""

            sym = build_es_symbol(
                new_symbol_name, geometry, es_pn, detail.mpn, detail.manufacturer or "",
                None, None, str(ratchaphruek + banmo), str(ratchaphruek), str(banmo),
                stock_date, price, str(detail.min_order_qty or ""), footprint_lib_id,
            )
            symbols_by_category.setdefault(category, []).append(sym)
            print(f"  {es_pn} -> {new_symbol_name} ({footprint_lib_id})")

    symbols_dst = out_dir / "symbols"
    symbols_dst.mkdir(parents=True, exist_ok=True)
    for category, syms in symbols_by_category.items():
        lib_content = '(kicad_symbol_lib\n\t(version 20231120)\n\t(generator "es-kicad-lib")\n\t(generator_version "8.0")\n'
        for s in syms:
            lib_content += s + "\n"
        lib_content += ")\n"
        (symbols_dst / f"ES-{category}.kicad_sym").write_text(lib_content, encoding="utf-8")

    return {"symbols_by_category": {k: len(v) for k, v in symbols_by_category.items()}, "footprints_copied": sorted(footprints_copied)}


if __name__ == "__main__":
    import datetime

    sys.path.insert(0, str(ROOT.parent / "es-parts-database"))
    from escrape.fetch import EsSession
    from escrape.parse_detail import parse_detail_html

    parser = argparse.ArgumentParser()
    parser.add_argument("--cdfer-repo", type=Path, required=True, help="path to a local clone of CDFER/JLCPCB-Kicad-Library")
    parser.add_argument("--out-dir", type=Path, default=ROOT)
    args = parser.parse_args()

    session = EsSession()
    stock_date = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    result = port(args.cdfer_repo, session, parse_detail_html, args.out_dir, stock_date)
    print(result)

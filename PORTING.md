# Porting notes — CDFER/JLCPCB-Kicad-Library → es-kicad-lib

Source: [CDFER/JLCPCB-Kicad-Library](https://github.com/CDFER/JLCPCB-Kicad-Library),
MIT licensed (Copyright (c) 2023 Chris). Studied at the commit fetched
2026-08-09. File-by-file disposition below; see plan.md §0.1 for why this
project forks it instead of writing a generator from scratch.

## Verbatim

- **`packageTools.py`** (37 lines) — `update_version()` writes
  `metadata.json`'s `versions` array; `create_zip_archive()` zips everything
  passed to it except files at or under `min_size_bytes` (default 128,
  strips empty placeholder files). No JLCPCB-specific logic in either
  function — ported unchanged as `generator/package_tools.py`.

## Reused (hand-drawn IC symbols and footprints, T2)

CDFER's ~48 hand-drawn IC-class symbols (`symbols/JLCPCB-{Analog,ICs,
Interface,MCUs,Memory,...}.kicad_sym`, drawn in KiCad's own Symbol Editor —
confirmed via each file's `(generator "kicad_symbol_editor")` /
`(generator "pcbnew")` header) are not code-generated in the reference
project either; there is no generic "draw N pins" function for T2 parts,
in CDFER or here. See plan.md §2.1's T1/T2/T3 tiers.

A part's pinout is a physical fact about the package, not JLCPCB-specific
data — an LM358's pin 1 is `1OUT` no matter which distributor sells it. So
where an ES catalogue row's MPN and package family match one of CDFER's
hand-drawn parts, the symbol's pin geometry (names/numbers/positions) and
the matching SOIC/SOP footprint's pad geometry are reused as-is; only the
sourcing properties (ES_PN, price, stock, description, ...) are replaced.

- **`mapping/cdfer_reuse.yaml`** — the curated match table. Every `es_pn`
  in it was confirmed live against es.co.th on 2026-08-09 with a
  package-compatible variant (SOIC/SOP matching CDFER's footprint, or
  PDIP mapped instead to KiCad's own stock `Package_DIP` footprint, plan
  §3.2 Route A) before being added — nothing in this table is guessed.
  MPN families with no package-compatible ES match, or where the ES
  catalogue's exact part number didn't exist at all (e.g. CDFER's
  STM8S003F3 vs. ES only stocking the unrelated STM8S003K3/LQFP-32), were
  dropped rather than force a wrong pairing (plan §3.5's confidence
  policy).
- **`generator/port_cdfer_reuse.py`** — the porting tool. Extracts each
  matched symbol's `(symbol "{name}_N_1" ...)` geometry sub-blocks
  byte-for-byte from a local CDFER clone, rebuilds a new symbol with the
  ES property schema wrapped around the unchanged geometry, and copies the
  matching Route B `.kicad_mod` into `footprints/ES.pretty/` (or points at
  a KiCad stock LIB_ID for the PDIP variants). One-shot, not part of the
  nightly pipeline — re-run manually when extending `cdfer_reuse.yaml`.
- Output validated end-to-end against real KiCad 10 (`kicad-cli sym export
  svg`): all 50 reused symbols across 4 library files load and render with
  zero errors, and spot-checking the LM358 render confirmed all 8 pin
  labels (`1OUT, 1IN-, 1IN+, GND, 2IN+, 2IN-, 2OUT, VCC`) came through
  correctly from the ported geometry.

## Adapted

- **`autoLibrarySymbols.py`** (1330 lines):
  - `generate_header`, `generate_property`, `generate_rectangle`,
    `generate_polyline`, `generate_pin_pair` — pure KiCad s-expression
    string builders, zero JLCPCB-specific content. Kept verbatim.
  - The hardcoded NPN/PNP/NMOS/PMOS symbol bodies (transistor geometry,
    ~800 of the 1330 lines) — kept verbatim; the geometry is a done problem
    regardless of parts-source.
  - `generate_kicad_symbol`'s `mode`/`secondary_mode` dispatch — six modes
    (Resistors, Capacitors, Diodes, Inductors, Transistors,
    Variable-Resistors) keyed off JLCPCB's own category taxonomy strings.
    **Rewritten** to key off ES `catc` codes instead (mapping table in
    `generator/catc_modes.py`), since ES's category tree has no relationship
    to JLCPCB's.
  - Field properties written per symbol (`LCSC`, `Stock`, `Price`, `Process`,
    `Minimum Qty`, `Attrition Qty`, `Class`, `Category`, `Manufacturer`,
    `Part`) — **rewritten** to the ES field schema in plan.md §2.4
    (`ES_PN`/`ES_URL` replace `LCSC`, `Stock_Ratchaphruek`/`Stock_BanMo`
    replace basic/preferred tiering, `Stock_Date` added, `Process`/
    `Attrition Qty`/`Class` dropped — no JLCPCB assembly-cost equivalent).
  - Footprint field value (`f"PCM_JLCPCB:{ref}_{footprint}"`) — **rewritten**
    per the Route A/B split in plan.md §3: Route A footprints resolve
    against KiCad's stock libraries (bare `LIB_ID`, no `PCM_JLCPCB:` prefix
    equivalent), Route B resolves against `ES.pretty`.

- **`libraryCreatorScript.py`** (818 lines):
  - `download_file()` — **kept, retargeted**: pulls
    `es-components.csv`/`es-parts.sqlite` from wherever `es-parts-database`
    publishes them (plan.md §1.5), same shape as CDFER's own
    `jlcpcb-components-basic-preferred.csv` pull.
  - Eight `extract_*_value` functions (`extract_capacitor_value`,
    `extract_resistance_value`, `extract_diode_type`,
    `extract_transistor_type`, `extract_LED_value`,
    `extract_inductor_type_value`, `extract_variable_resistor_type_value`,
    `extract_capacitor_voltage`) — regex over free-text descriptions because
    JLCPCB's source data has no parametric columns. **Dropped entirely.**
    ES's `af.asp` gives real parametric columns (`Resistance in Ohms`,
    `Tolerance`, `Power (Watts)`, etc. — confirmed against a live sample in
    es-parts-database/tests/fixtures/af_resistors.html); reading a named
    column beats parsing prose. This removes CDFER's largest single source
    of technical debt, per plan.md's explicit callout.
  - `get_basic_or_prefered_type()` — JLCPCB's basic/preferred/extended
    tiering has no ES equivalent (ES has no such distributor-assigned tier).
    **Dropped**; ES's closest analogous axis is warehouse
    (Ratchaphruek/immediate vs Ban Mo/+2 days), which is a property, not a
    generation-mode input.
  - `generate_kicad_symbol_libs()` — **kept, retargeted**: same
    `(kicad_symbol_lib ...)` wrapper and per-library file write, filename
    prefix changes from `JLCPCB-` to `ES-`.
  - `check_models()` / `check_footprints()` — **kept, extended**: same
    archive-move dance (unused assets → `Archived-Symbols-Footprints/`,
    needed-but-archived assets move back), same guarantee ("every name we
    emitted exists"). Extended per plan.md §3.4 to handle two footprint
    backends: Route A resolves against KiCad's installed stock footprint
    libraries, Route B resolves against `ES.pretty` exactly as CDFER
    resolves against `JLCPCB.pretty`.
  - The main CSV-to-symbol driver loop (lines ~600–700, calls the
    `extract_*` functions and assembles `generate_kicad_symbol()` args) —
    **rewritten** around ES's parametric columns and `catc`-keyed mode
    dispatch.

- **`handmadeLibrarySymbols.py`** (135 lines) — pure text-surgery on
  committed `.kicad_sym` files, no JLCPCB-specific data model beyond the
  `LCSC`/`Stock` property names it searches for:
  - `update_component_inplace(lcsc, libraryName, properties)` — **adapted**
    to `update_component_inplace(es_pn, libraryName, properties)`, searches
    for `(property "ES_PN" "..."` instead of `(property "LCSC" "C..."`.
    Same line-walking approach (work upward from the match for
    Datasheet/Description, work downward for the rest, insert before
    `ki_keywords` if a property wasn't found in place).
  - `update_library_stock_inplace(libraryName)` — **adapted**: reads
    `es-components.csv` instead of `jlcpcb-components-basic-preferred.csv`,
    matches on `es_pn` instead of `lcsc`. Same archive-on-zero-stock
    behavior via `create_archived_symbol_file`.
  - `generate_property()` / `create_archived_symbol_file()` — kept
    verbatim, no JLCPCB-specific content.

## Dropped

- LCSC ID handling throughout (`f"C{lcsc}"` formatting, JLCPCB partdetail
  URLs in error messages) — replaced by ES P/N (`0102-0108-2` format) and
  `detail.asp?Prod=<dashes-stripped>` URLs.
- Assembly/joint-cost pricing fields (`Process`, `Attrition Qty`,
  `assembly_process`, `min_order_qty` as an *assembly* concept) — ES is a
  distributor with list pricing, not a fab with assembly service pricing.
  ES's own MOQ (from `detail.asp`, plan.md §1.3) is a different concept and
  is kept as `Min Order Qty`.
- `get_basic_or_prefered_type()` and all basic/preferred/extended framing —
  see above.
- `LLM-Check-Pinswaps.ipynb` — not ported now; noted in plan.md §0.1 and
  §2.5 to revisit for T2 hand-drawn IC symbols once those exist.

## Attribution

Every file carrying ported CDFER code keeps a header comment crediting the
source repository and its MIT license. The MIT license text itself is
reproduced in `LICENSE` (this repo is also MIT) with the CDFER copyright
notice preserved per the license's own terms.

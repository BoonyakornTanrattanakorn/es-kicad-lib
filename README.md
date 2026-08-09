# es-kicad-lib

A KiCad library of Electronics Source (es.co.th) parts: symbols,
footprints, 3D models, and sourcing fields (ES P/N, price, stock). See
`../plan.md` for the full project plan and `PORTING.md` for exactly what
was forked from [CDFER/JLCPCB-Kicad-Library](https://github.com/CDFER/JLCPCB-Kicad-Library)
(MIT) versus rewritten.

Consumes `es-components.csv` / `es-parts.sqlite` published by
[`../es-parts-database`](../es-parts-database) — that repo does the
scraping, this one only generates symbols/footprints/packages from
already-published data.

## Parts search

`docs/` is a static, client-side parts search over the same catalogue,
served via GitHub Pages at
`https://boonyakorntanrattanakorn.github.io/es-kicad-lib/`. DigiKey-style
three-pane layout: category tree, results table, and faceted filters
(numeric ranges and checkboxes) built from each part's parametric spec
table.

- `docs/index.html` / `docs/search.css` / `docs/search.js` — the page.
  No build step, no backend; everything runs in the browser against
  static JSON.
- `docs/data/index.json` + `docs/data/{category}.json` — one JSON file
  per second-level category (e.g. `passive-components-resistors.json`),
  generated from `es-parts.sqlite` by
  [`escrape.export_search_json`](../es-parts-database/escrape/export_search_json.py)
  in `es-parts-database`. Lazy-loaded per category so the browser never
  downloads the full catalogue up front.
- Regenerate after a new `es-parts.sqlite` is published:
  ```
  cd ../es-parts-database
  python -m escrape.export_search_json --out ../es-kicad-lib/docs/data
  ```
  Commit the regenerated `docs/data/*.json` alongside the next release —
  same cadence as the `metadata.json` version bump in
  `generator/package.py`.

## Layout

- `generator/package_tools.py` — ported verbatim from CDFER: `.zip`
  archiving (`create_zip_archive`) and `metadata.json` version bumping
  (`update_version`).
- `generator/autoLibrarySymbols.py` — geometry helpers and hardcoded
  transistor/inductor/fuse body literals kept verbatim from CDFER;
  `generate_kicad_symbol()`'s property schema rewritten to the ES field set
  (`ES_PN`, `ES_URL`, `Stock_Ratchaphruek`, `Stock_BanMo`, `Stock_Date`, ...
  — see plan.md §2.4). Mode dispatch itself (Resistors/Capacitors/Diodes/
  Inductors/Transistors/Variable-Resistors) is unchanged; what changed is
  *what decides* the mode — see `catc_modes.py`.
- `generator/catc_modes.py` — maps ES `catc` leaf codes to
  `(mode, secondary_mode)`, replacing CDFER's dispatch off JLCPCB's own
  category-name strings.
- `generator/value_extraction.py` — reads ES's parametric columns
  (`Resistance in Ohms`, `Capacitance`, `Zener Voltage`, ...) to get the
  `value`/`secondary_mode` generate_kicad_symbol needs. Replaces CDFER's
  eight `extract_*_value` regex-over-description functions entirely — ES's
  source data has real columns, so there's no prose to parse. This is the
  single biggest simplification versus the reference implementation.
- `generator/build_symbols.py` — the driver: reads `es-parts.sqlite`,
  dispatches each row through `catc_modes.py` + `value_extraction.py`, and
  writes `symbols/ES-{lib_name}.kicad_sym` files via `library_writer.py`.
  Only handles T1 (fully auto-generated) categories; anything with no
  `catc_modes.py` entry is skipped — those are T2/T3 (plan §2.1).
- `generator/footprint_map.py` + `mapping/footprint_map.yaml` — Route A
  footprint resolution (plan §3.2): maps `{ref_designator}_{pkg_case}` to a
  KiCad stock `LIB_ID` (e.g. `Resistor_SMD:R_0402_1005Metric`), checked
  against a real KiCad 10 install before being added. Only common,
  unambiguous packages are mapped; anything absent falls through to an
  `ES:{name}` placeholder rather than guessing — that placeholder is what
  `library_checks.check_footprints()` (Route B) or a future manual mapping
  entry is meant to resolve later.
- `generator/library_writer.py` — `generate_kicad_symbol_libs()`, ported
  from CDFER with the filename prefix changed `JLCPCB-` → `ES-`.
- `generator/handmade_symbols.py` — update-in-place for T2 hand-drawn
  symbols: `update_component_inplace()` patches one part's property values
  by ES_PN without touching its hand-drawn geometry;
  `update_library_stock_inplace()` zeroes stock for parts that dropped out
  of the latest catalogue and archives them once they hit zero.
- `generator/library_checks.py` — referential integrity with auto-archive
  (plan §3.4): `check_footprints()` resolves every symbol's `Footprint`
  property against either Route A (a caller-supplied set of KiCad stock
  `LIB_ID`s) or Route B (`ES:{name}` against `footprints/ES.pretty`);
  `check_models()` resolves Route B footprints' 3D model references
  against `3dmodels/ES.3dshapes`. Unused assets move to
  `Archived-Symbols-Footprints/`; newly-needed ones move back.
- `generator/package.py` — packaging entry point (plan §4.1): bumps
  `metadata.json`'s version to today's UTC date and zips
  `3dmodels`/`footprints`/`resources`/`symbols`/`metadata.json` into a
  PCM-installable archive.
- `generator/port_cdfer_reuse.py` + `mapping/cdfer_reuse.yaml` — reuses
  CDFER's ~48 hand-drawn IC symbols (op-amps, comparators, logic gates,
  RS232/RS485/CAN transceivers, shift registers, an ATmega328P, SPI flash)
  for ES catalogue rows with a matching MPN and package. See PORTING.md's
  "Reused" section for the safety rationale and match-verification
  process. One-shot tool, not part of the nightly pipeline.

## Installing

### Option A: Add as a PCM repository (recommended)

1. In KiCad, open **Plugin and Content Manager** (puzzle-piece icon on the
   main toolbar).
2. Click the gear icon → **Manage Repositories** → **Add**.
3. Enter this URL:
   ```
   https://raw.githubusercontent.com/BoonyakornTanrattanakorn/es-kicad-lib/master/repository.json
   ```
4. Select the "Electronics Source (es.co.th) Parts Library" package under
   the new repository and click **Install**.

`repository.json` and `packages.json` are checked into this repo's root
and served via `raw.githubusercontent.com`, so no separate hosting is
needed. **After cutting a new release**, `packages.json`'s `download_url`/
`download_sha256`/`download_size` must be updated to match the new
release asset, and `repository.json`'s `packages.sha256` /
`update_timestamp` must be recomputed against the new `packages.json` —
`generator/package.py` does not currently automate this (plan §4.1).

### Option B: Install from a release zip manually

1. Download the latest `es-kicad-lib-*.zip` from the
   [Releases page](https://github.com/BoonyakornTanrattanakorn/es-kicad-lib/releases).
2. In KiCad, open **Plugin and Content Manager**, click **Install from
   File**, and select the downloaded zip.
3. Enable the library and restart KiCad if prompted.

Symbols, footprints, and 3D models are then available under the `ES`
prefix in the symbol/footprint choosers.

## Running

```
pip install -r requirements.txt

# Generate T1 symbols from a published es-parts.sqlite:
python -m generator.build_symbols --db ../es-parts-database/out/es-parts.sqlite

# Package the current symbols/footprints/3dmodels into a PCM zip:
python -m generator.package
```

## Tests

```
python -m pytest tests/ -q
```

Tests run offline against `tests/fixtures/` — a real `es-parts.sqlite`
sample (73 parts: resistors, ceramic capacitors, zener diodes, harvested
2026-08-09) and a real generated `.kicad_sym` fixture, so the symbol
generator and the update-in-place mechanism are both tested against actual
data rather than synthetic stand-ins.

Symbol output has also been validated end-to-end against real KiCad 10
(`kicad-cli sym export svg`) — every generated symbol across Resistors,
Capacitors, and Diodes libraries loads and renders with zero parse errors.

## Not yet done

- T2 hand-drawn symbols (regulators, op-amps, logic, connectors, MCUs, ...)
  — plan Phase 2.1 tier 2. `catc_modes.py` intentionally has no entries for
  these catc codes; `handmade_symbols.py` is ready to patch them once
  they're drawn.
- Footprints and 3D models (`footprints/ES.pretty`, `3dmodels/ES.3dshapes`)
  — plan Phase 3. `library_checks.py` is written and tested against a
  synthetic layout but has never run against a real footprint set.
- Package canonicalisation (`package_aliases.yaml`, plan §3.1) and the
  Route A/B mapping table (plan §3.2-3.3).
- PCM repository JSON hosting (plan §4.1) and the `.kicad_dbl` database
  library (plan §4.2, optional).
- Nightly rebuild automation and alerting (plan Phase 5).

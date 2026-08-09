"""Referential integrity checks with auto-archive (plan §2.1 point 4, §3.4):
every symbol's Footprint property must resolve to a real footprint, and
every footprint's 3D model reference must resolve to a real .step file.
Unused assets move to Archived-Symbols-Footprints/; newly-needed ones move
back. The guarantee is "every name we emitted exists," not "we matched
correctly."

Adapted from CDFER/JLCPCB-Kicad-Library's check_footprints()/check_models()
(MIT licensed, Copyright (c) 2023 Chris). See PORTING.md.

Extended per plan §3.4 for two footprint backends instead of one:
  - Route A: Footprint property has no "ES:" prefix removed by the caller
    here — it's a bare LIB_ID meant to resolve against KiCad's own stock
    footprint libraries (Package_SO, Resistor_SMD, ...). This module treats
    any Footprint value not found in ES.pretty and not archived as Route A
    and checks it against the caller-supplied set of installed stock
    footprint LIB_IDs (resolve_stock_footprints), rather than assuming it's
    missing.
  - Route B: Footprint value is "ES:{name}", resolved against ES.pretty
    exactly as CDFER resolves PCM_JLCPCB: against JLCPCB.pretty.
"""
import re
import shutil
from pathlib import Path


def _kicad_mod_names(folder: Path) -> list[str]:
    if not folder.exists():
        return []
    return [p.stem for p in folder.glob("*.kicad_mod")]


def _step_names(folder: Path) -> list[str]:
    if not folder.exists():
        return []
    return [p.stem for p in folder.glob("*.step")]


def check_footprints(
    symbols_dir: Path,
    footprints_dir: Path,
    archived_footprints_dir: Path,
    stock_footprint_lib_ids: set[str] | None = None,
) -> list[str]:
    """Returns a list of problem messages; empty means everything resolved.
    stock_footprint_lib_ids: LIB_IDs (e.g. "Resistor_SMD:R_0402_1005Metric")
    considered valid Route A targets, supplied by the caller since resolving
    KiCad's installed footprint libraries is environment-specific.
    """
    stock_footprint_lib_ids = stock_footprint_lib_ids or set()
    problems: list[str] = []

    archived_footprint_names = _kicad_mod_names(archived_footprints_dir)
    footprint_names = _kicad_mod_names(footprints_dir)
    footprint_names_used: list[str] = []

    for symbol_lib_path in sorted(symbols_dir.glob("*.kicad_sym")):
        symbol_name = None
        with symbol_lib_path.open("r", encoding="utf-8") as file:
            for line in file:
                match = re.search(r'\(symbol "([^"]+)"', line)
                if match:
                    symbol_name = match.group(1)
                    continue

                match = re.search(r'\(property "Footprint" "([^"]+)"', line)
                if not match:
                    continue
                footprint_value = match.group(1)
                if not footprint_value:
                    problems.append(f"Empty Footprint property for symbol {symbol_name} ({symbol_lib_path.name})")
                    continue

                route_b_match = re.match(r"^ES:(.+)$", footprint_value)
                if route_b_match:
                    footprint_name = route_b_match.group(1)
                    if footprint_name in footprint_names:
                        footprint_names_used.append(footprint_name)
                    elif footprint_name in archived_footprint_names:
                        pre = archived_footprints_dir / f"{footprint_name}.kicad_mod"
                        post = footprints_dir / f"{footprint_name}.kicad_mod"
                        shutil.move(str(pre), str(post))
                        archived_footprint_names.remove(footprint_name)
                        footprint_names_used.append(footprint_name)
                        print(f"Un-archived needed footprint: {footprint_name}")
                    else:
                        problems.append(
                            f"Missing Route B footprint for symbol {symbol_name} -> {footprint_value} ({symbol_lib_path.name})"
                        )
                elif footprint_value in stock_footprint_lib_ids:
                    pass  # Route A, resolved against KiCad's stock libraries
                else:
                    problems.append(
                        f"Unresolved footprint for symbol {symbol_name} -> {footprint_value} ({symbol_lib_path.name}); "
                        "not in ES.pretty, its archive, or the supplied stock LIB_ID set"
                    )

    for footprint in footprint_names:
        if footprint not in footprint_names_used:
            pre = footprints_dir / f"{footprint}.kicad_mod"
            post = archived_footprints_dir / f"{footprint}.kicad_mod"
            shutil.move(str(pre), str(post))
            print(f"Archived unused footprint: {footprint}")

    return problems


def check_models(
    footprints_dir: Path,
    models_dir: Path,
    archived_models_dir: Path,
    model_path_re: re.Pattern = re.compile(r"/3dmodels/ES\.3dshapes/([^\"]+)\.step"),
    exempt_footprints: tuple[str, ...] = (),
) -> list[str]:
    """Route B only: Route A footprints carry their own 3D models from
    KiCad's stock libraries and aren't checked here (plan §3.4: "Adapt
    check_models() unchanged for Route B")."""
    problems: list[str] = []

    footprint_names = _kicad_mod_names(footprints_dir)
    archived_model_names = _step_names(archived_models_dir)
    model_names = _step_names(models_dir)
    model_names_used: list[str] = []

    for footprint_name in footprint_names:
        footprint_path = footprints_dir / f"{footprint_name}.kicad_mod"
        content = footprint_path.read_text(encoding="utf-8")
        match = re.search(r'\(model "([^"]+)"', content)

        if match:
            model_path = match.group(1)
            model_match = model_path_re.search(model_path)
            if model_match:
                model = model_match.group(1)
                if model not in model_names:
                    if model in archived_model_names:
                        pre = archived_models_dir / f"{model}.step"
                        post = models_dir / f"{model}.step"
                        shutil.move(str(pre), str(post))
                        archived_model_names.remove(model)
                        print(f"Un-archived needed model: {model}")
                    else:
                        problems.append(f"Missing 3D model for footprint {footprint_name} ({model_path})")
                else:
                    model_names_used.append(model)
            else:
                problems.append(f"Incorrect model path for footprint {footprint_name} ({model_path})")
        elif footprint_name not in exempt_footprints:
            problems.append(f"Empty model field for footprint {footprint_name}")

    for model in model_names:
        if model not in model_names_used:
            pre = models_dir / f"{model}.step"
            post = archived_models_dir / f"{model}.step"
            shutil.move(str(pre), str(post))
            print(f"Archived unused model: {model}")

    return problems

from pathlib import Path

import pytest

from generator.library_checks import check_footprints, check_models


def _write_symbol_lib(path: Path, name: str, footprint_value: str):
    path.write_text(
        f"""(kicad_symbol_lib
\t(symbol "{name}"
\t\t(property "Footprint" "{footprint_value}"
\t\t\t(at -1.778 0 90)
\t\t)
\t)
)
""",
        encoding="utf-8",
    )


@pytest.fixture
def layout(tmp_path):
    symbols = tmp_path / "symbols"
    footprints = tmp_path / "footprints" / "ES.pretty"
    archived_footprints = tmp_path / "Archived-Symbols-Footprints" / "ES-Footprints"
    models = tmp_path / "3dmodels" / "ES.3dshapes"
    archived_models = tmp_path / "Archived-Symbols-Footprints" / "3dModels"
    for d in (symbols, footprints, archived_footprints, models, archived_models):
        d.mkdir(parents=True)
    return {
        "symbols": symbols,
        "footprints": footprints,
        "archived_footprints": archived_footprints,
        "models": models,
        "archived_models": archived_models,
    }


def test_check_footprints_route_b_resolved_no_problems(layout):
    (layout["footprints"] / "R_0402.kicad_mod").write_text("(footprint)", encoding="utf-8")
    _write_symbol_lib(layout["symbols"] / "ES-Resistors.kicad_sym", "0402,10K", "ES:R_0402")

    problems = check_footprints(layout["symbols"], layout["footprints"], layout["archived_footprints"])
    assert problems == []


def test_check_footprints_route_b_missing_is_reported(layout):
    _write_symbol_lib(layout["symbols"] / "ES-Resistors.kicad_sym", "0402,10K", "ES:R_0402")

    problems = check_footprints(layout["symbols"], layout["footprints"], layout["archived_footprints"])
    assert len(problems) == 1
    assert "Missing Route B footprint" in problems[0]


def test_check_footprints_unarchives_needed_footprint(layout):
    (layout["archived_footprints"] / "R_0402.kicad_mod").write_text("(footprint)", encoding="utf-8")
    _write_symbol_lib(layout["symbols"] / "ES-Resistors.kicad_sym", "0402,10K", "ES:R_0402")

    problems = check_footprints(layout["symbols"], layout["footprints"], layout["archived_footprints"])
    assert problems == []
    assert (layout["footprints"] / "R_0402.kicad_mod").exists()
    assert not (layout["archived_footprints"] / "R_0402.kicad_mod").exists()


def test_check_footprints_archives_unused_footprint(layout):
    (layout["footprints"] / "R_0603.kicad_mod").write_text("(footprint)", encoding="utf-8")
    # no symbol references R_0603 at all

    check_footprints(layout["symbols"], layout["footprints"], layout["archived_footprints"])

    assert not (layout["footprints"] / "R_0603.kicad_mod").exists()
    assert (layout["archived_footprints"] / "R_0603.kicad_mod").exists()


def test_check_footprints_route_a_resolved_against_stock_lib_ids(layout):
    _write_symbol_lib(
        layout["symbols"] / "ES-Resistors.kicad_sym",
        "0402,10K",
        "Resistor_SMD:R_0402_1005Metric",
    )

    problems = check_footprints(
        layout["symbols"],
        layout["footprints"],
        layout["archived_footprints"],
        stock_footprint_lib_ids={"Resistor_SMD:R_0402_1005Metric"},
    )
    assert problems == []


def test_check_footprints_route_a_unresolved_is_reported(layout):
    _write_symbol_lib(
        layout["symbols"] / "ES-Resistors.kicad_sym",
        "0402,10K",
        "Resistor_SMD:R_0402_1005Metric",
    )

    problems = check_footprints(layout["symbols"], layout["footprints"], layout["archived_footprints"])
    assert len(problems) == 1
    assert "Unresolved footprint" in problems[0]


def _write_footprint_with_model(path: Path, model_step_name: str):
    path.write_text(
        f'(footprint "X"\n  (model "${{KIPRJMOD}}/3dmodels/ES.3dshapes/{model_step_name}.step"\n  )\n)',
        encoding="utf-8",
    )


def test_check_models_resolved_no_problems(layout):
    _write_footprint_with_model(layout["footprints"] / "R_0402.kicad_mod", "R_0402")
    (layout["models"] / "R_0402.step").write_text("STEP", encoding="utf-8")

    problems = check_models(layout["footprints"], layout["models"], layout["archived_models"])
    assert problems == []


def test_check_models_missing_is_reported(layout):
    _write_footprint_with_model(layout["footprints"] / "R_0402.kicad_mod", "R_0402")

    problems = check_models(layout["footprints"], layout["models"], layout["archived_models"])
    assert len(problems) == 1
    assert "Missing 3D model" in problems[0]


def test_check_models_unarchives_needed_model(layout):
    _write_footprint_with_model(layout["footprints"] / "R_0402.kicad_mod", "R_0402")
    (layout["archived_models"] / "R_0402.step").write_text("STEP", encoding="utf-8")

    problems = check_models(layout["footprints"], layout["models"], layout["archived_models"])
    assert problems == []
    assert (layout["models"] / "R_0402.step").exists()


def test_check_models_archives_unused_model(layout):
    (layout["models"] / "R_0603.step").write_text("STEP", encoding="utf-8")
    # no footprint references R_0603.step

    check_models(layout["footprints"], layout["models"], layout["archived_models"])

    assert not (layout["models"] / "R_0603.step").exists()
    assert (layout["archived_models"] / "R_0603.step").exists()


def test_check_models_exempt_footprint_skips_empty_model_warning(layout):
    (layout["footprints"] / "Hole_3mm.kicad_mod").write_text("(footprint)", encoding="utf-8")

    problems = check_models(
        layout["footprints"], layout["models"], layout["archived_models"], exempt_footprints=("Hole_3mm",)
    )
    assert problems == []

"""Per-mode value/secondary_mode extraction from ES parametric columns.

This is the ES-native replacement for CDFER's eight extract_*_value regex
functions (extract_resistance_value, extract_capacitor_value,
extract_diode_type, ...), dropped per PORTING.md: ES's af.asp gives real
parametric columns, so extraction here is a dict lookup with light
formatting, not prose parsing. Each function takes the merged specs dict
(parts.specs_json, plan §1.4) and the row's category/description as a
fallback, and returns (value, secondary_mode) — secondary_mode is None
where generate_kicad_symbol doesn't need one beyond what catc_modes.py
already fixed.
"""
import re
from typing import Optional


def _first(specs: dict, *keys: str) -> Optional[str]:
    for k in keys:
        v = specs.get(k)
        if v and v != "-":
            return v
    return None


def extract_resistance_value(specs: dict) -> str:
    return _first(specs, "Resistance in Ohms", "Resistance") or "?"


def extract_capacitor_value(specs: dict) -> str:
    return _first(specs, "Capacitance") or "?"


def extract_capacitor_voltage(specs: dict) -> Optional[str]:
    return _first(specs, "Voltage-Rated", "Voltage Rated", "Rated Voltage")


ZENER_SUFFIX_RE = re.compile(r"C13|Case 13|SOD-123", re.I)


def extract_diode_secondary_mode(specs: dict, catc_secondary_mode: Optional[str], mfr_package: Optional[str]) -> Optional[str]:
    """catc_modes.py already fixes the coarse family (Zener/Schottky/TVS/LED)
    for most diode catc codes; this only resolves the finer C13-package
    variant CDFER's extract_diode_type distinguished (Zener13/Schottky13),
    based on the package column rather than regex over a description.
    """
    if catc_secondary_mode == "Zener" and mfr_package and ZENER_SUFFIX_RE.search(mfr_package):
        return "Zener13"
    if catc_secondary_mode == "Schottky" and mfr_package and ZENER_SUFFIX_RE.search(mfr_package):
        return "Schottky13"
    if catc_secondary_mode == "TVS-Uni" and "bi" in (specs.get("Configuration") or specs.get("Type") or "").lower():
        return "TVS-Bi"
    return catc_secondary_mode


def extract_diode_value(specs: dict, secondary_mode: Optional[str]) -> str:
    if secondary_mode in ("Zener", "Zener13"):
        return _first(specs, "Zener Voltage") or "?"
    if secondary_mode in ("Schottky", "Schottky13"):
        return _first(specs, "Forward Voltage", "Reverse Voltage") or "?"
    if secondary_mode in ("TVS-Uni", "TVS-Bi"):
        return _first(specs, "Reverse Standoff Voltage", "Breakdown Voltage") or "?"
    return _first(specs, "Reverse Voltage", "Forward Voltage") or "?"


def extract_led_value_and_color(specs: dict) -> tuple[str, str]:
    color = _first(specs, "Emitted Color", "Color") or "?"
    secondary_mode = "LED-Bi-Colour" if "bi" in color.lower() or "," in color else "LED"
    return color, secondary_mode


def extract_transistor_secondary_mode(catc: str, specs: dict) -> Optional[str]:
    """catc 024011 (Transistors) is NPN/PNP; 024014 (FETs & MOSFETs) is
    NMOS/PMOS. Distinguished by the 'Polarity'/'Transistor Type' column
    rather than joint-count heuristics (CDFER used pin count + package
    since JLCPCB's source data has no polarity column; ES's does).
    """
    polarity = (_first(specs, "Polarity", "Transistor Type", "Channel Type") or "").upper()
    if catc == "024011":
        if "PNP" in polarity:
            return "PNP"
        return "NPN"
    if catc == "024014":
        if "P-CHANNEL" in polarity or "PMOS" in polarity or polarity == "P":
            return "PMOS"
        return "NMOS"
    return None


def extract_transistor_value(specs: dict) -> str:
    return _first(specs, "Manufacturer Part Number", "Series") or "?"


def extract_inductor_secondary_mode_and_value(catc: str, specs: dict) -> tuple[Optional[str], str]:
    if catc in ("020003003", "013002005"):
        return "Ferrite", _first(specs, "Impedance") or "?"
    return "Inductor", _first(specs, "Inductance") or "?"


def extract_variable_resistor_secondary_mode_and_value(catc: str, specs: dict) -> tuple[Optional[str], str]:
    if catc == "013004004":
        resettable = "resettable" in (specs.get("Fuse Type") or "").lower()
        return ("Fuse,Resettable" if resettable else "Fuse"), (_first(specs, "Current Rating", "Fuse Current") or "?")
    if catc == "013004005":
        return "MOV", _first(specs, "Varistor Voltage", "AC Voltage Rating") or "?"
    if catc == "020007":
        return "NTC", _first(specs, "Resistance", "Resistance in Ohms") or "?"
    return None, "?"

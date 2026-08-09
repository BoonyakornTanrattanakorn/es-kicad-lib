"""Maps ES catc leaf codes to autoLibrarySymbols.generate_kicad_symbol's
mode/secondary_mode dispatch (plan §2.2 — "rewrite the mode dispatch to key
off ES catc codes instead of JLCPCB category names").

Only T1 categories per plan §2.1 appear here (fully auto-generated:
resistors, caps, inductors, ferrites, diodes, zeners, Schottkys, TVS, LEDs,
BJTs, MOSFETs, crystals, fuses, varistors, NTCs). T2/T3 categories
(regulators, op-amps, MCUs, connectors, relays, displays, ...) are absent —
crawl_and_generate should route those to the handmade/stock-patched path
instead of calling generate_kicad_symbol at all.

catc codes and names cross-checked against
es-parts-database/mapping/catc_allowlist.yaml (2026-08-09).
"""

# catc -> (mode, secondary_mode). secondary_mode is None where
# generate_kicad_symbol doesn't need one (Resistors, plain Diodes handled
# via description/parametric sniffing at the caller instead — see NOTE
# below for the diode family, which needs a value, not just a catc lookup).
CATC_MODE = {
    # Resistors
    "020006001": ("Resistors", None),  # Resistor Network / Array
    "020006002": ("Resistors", None),  # SMT Resistor
    "020006003": ("Resistors", None),  # Through Hole Resistor
    # Capacitors
    "020001001": ("Capacitors", None),  # Ceramic Capacitors
    "020001003": ("Capacitors", None),  # Electrolytic Capacitors
    "020001004": ("Capacitors", None),  # Film Capacitors
    "020001005": ("Capacitors", None),  # Tantalum Capacitors
    # Inductors / ferrites
    "020004001": ("Inductors", "Inductor"),  # Fixed Inductors
    "020003003": ("Inductors", "Ferrite"),  # Ferrite Beads & Chips for EMI
    "013002005": ("Inductors", "Ferrite"),  # Ferrite Core
    # Diodes: catc alone picks the family; LED vs plain still needs the
    # per-row description/parametrics to pick LED / LED-Bi-Colour / Zener13 /
    # Schottky13 sub-variants, same as CDFER's extract_diode_type did off
    # prose — here it's a lookup against the "Series"/"Product Type"
    # parametric column instead of a regex, done by the caller.
    "024003002": ("Diodes", "Zener"),  # Zener Diode
    "024003003": ("Diodes", "TVS-Uni"),  # TVS Diode (bi/uni resolved by caller)
    "024003005": ("Diodes", None),  # Standard Recovery Diode
    "024003006": ("Diodes", None),  # Fast Recovery Diode
    "024003007": ("Diodes", None),  # Small Signal Switching Diode
    "024003008": ("Diodes", None),  # Current Regulating Diode
    "024003009": ("Diodes", "Schottky"),  # Schottky Diode
    "015016": ("Diodes", "LED"),  # LED Discrete
    # Transistors
    "024011": ("Transistors", None),  # Transistors (NPN/PNP resolved by caller)
    "024014": ("Transistors", None),  # FETs & MOSFETs (NMOS/PMOS resolved by caller)
    "034022": ("Transistors", None),  # Transistor Arrays
    # Variable resistors / fuses / varistors / thermistors
    "013004004": ("Variable-Resistors", "Fuse"),  # Fuses
    "013004005": ("Variable-Resistors", "MOV"),  # Varistor, MOVs
    "020007": ("Variable-Resistors", "NTC"),  # Thermistors
}


def lookup_mode(catc: str) -> tuple[str, str] | None:
    return CATC_MODE.get(catc)

from generator.catc_modes import CATC_MODE, lookup_mode


def test_resistor_catc_maps_to_resistors_mode():
    assert lookup_mode("020006002") == ("Resistors", None)


def test_zener_diode_catc_maps_to_diodes_zener():
    assert lookup_mode("024003002") == ("Diodes", "Zener")


def test_unknown_catc_returns_none():
    assert lookup_mode("999999999") is None


def test_every_entry_has_a_valid_mode():
    valid_modes = {"Resistors", "Capacitors", "Diodes", "Inductors", "Transistors", "Variable-Resistors"}
    for catc, (mode, secondary_mode) in CATC_MODE.items():
        assert mode in valid_modes, f"{catc} has unexpected mode {mode}"

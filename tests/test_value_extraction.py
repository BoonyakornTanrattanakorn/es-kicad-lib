from generator.value_extraction import (
    extract_capacitor_value,
    extract_capacitor_voltage,
    extract_diode_secondary_mode,
    extract_diode_value,
    extract_inductor_secondary_mode_and_value,
    extract_resistance_value,
    extract_transistor_secondary_mode,
    extract_variable_resistor_secondary_mode_and_value,
)


def test_extract_resistance_value_reads_named_column():
    assert extract_resistance_value({"Resistance in Ohms": "47KΩ"}) == "47KΩ"


def test_extract_resistance_value_missing_returns_placeholder():
    assert extract_resistance_value({}) == "?"


def test_extract_capacitor_value_and_voltage():
    specs = {"Capacitance": "22μF", "Voltage-Rated": "10V"}
    assert extract_capacitor_value(specs) == "22μF"
    assert extract_capacitor_voltage(specs) == "10V"


def test_extract_capacitor_voltage_ignores_dash_placeholder():
    assert extract_capacitor_voltage({"Voltage-Rated": "-"}) is None


def test_extract_diode_secondary_mode_resolves_c13_zener_variant():
    result = extract_diode_secondary_mode({}, "Zener", "SOD-123")
    assert result == "Zener13"


def test_extract_diode_secondary_mode_plain_zener_stays_plain():
    result = extract_diode_secondary_mode({}, "Zener", "DO-35 (DO-204AH)")
    assert result == "Zener"


def test_extract_diode_value_zener_reads_zener_voltage():
    assert extract_diode_value({"Zener Voltage": "3.6V"}, "Zener") == "3.6V"


def test_extract_transistor_secondary_mode_npn_default():
    assert extract_transistor_secondary_mode("024011", {}) == "NPN"


def test_extract_transistor_secondary_mode_pnp_from_polarity():
    assert extract_transistor_secondary_mode("024011", {"Polarity": "PNP"}) == "PNP"


def test_extract_transistor_secondary_mode_mosfet_nmos_default():
    assert extract_transistor_secondary_mode("024014", {}) == "NMOS"


def test_extract_transistor_secondary_mode_mosfet_pmos():
    assert extract_transistor_secondary_mode("024014", {"Channel Type": "P-Channel"}) == "PMOS"


def test_extract_inductor_ferrite_vs_plain():
    mode, value = extract_inductor_secondary_mode_and_value("013002005", {"Impedance": "100Ω"})
    assert mode == "Ferrite"
    assert value == "100Ω"

    mode, value = extract_inductor_secondary_mode_and_value("020004001", {"Inductance": "10μH"})
    assert mode == "Inductor"
    assert value == "10μH"


def test_extract_variable_resistor_fuse_vs_ntc():
    mode, value = extract_variable_resistor_secondary_mode_and_value("013004004", {"Current Rating": "500mA"})
    assert mode == "Fuse"
    assert value == "500mA"

    mode, value = extract_variable_resistor_secondary_mode_and_value("020007", {"Resistance": "10KΩ"})
    assert mode == "NTC"
    assert value == "10KΩ"

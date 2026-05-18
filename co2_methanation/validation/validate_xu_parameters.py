"""Quick checks for the Xu-Froment parameter implementation."""

from __future__ import annotations

import math

from kinetics.xu_froment1989 import adsorption_constants, kinetic_constants, reaction_rates


def main() -> None:
    kinetics_648 = kinetic_constants(648.0)
    adsorption_648 = adsorption_constants(648.0)
    adsorption_823 = adsorption_constants(823.0)

    # Table 5 reference-temperature checks. Small mismatch is expected because
    # Table 6 values are rounded preexponential factors.
    assert math.isclose(kinetics_648["k1"], 1.842e-4, rel_tol=0.02)
    assert math.isclose(kinetics_648["k2"], 7.558, rel_tol=0.01)
    assert math.isclose(kinetics_648["k3"], 2.193e-5, rel_tol=0.02)
    assert math.isclose(adsorption_648["CO"], 40.91, rel_tol=0.01)
    assert math.isclose(adsorption_648["H2"], 0.02960, rel_tol=0.01)
    assert math.isclose(adsorption_823["CH4"], 0.1791, rel_tol=0.01)
    assert math.isclose(adsorption_823["H2O"], 0.4152, rel_tol=0.01)

    partial_pressures_bar = {
        "CO2": 5.0,
        "H2": 20.0,
        "CH4": 0.2,
        "H2O": 0.2,
        "CO": 0.05,
    }

    print("kinetic_constants_648", kinetics_648)
    print("adsorption_constants_648", adsorption_648)
    print("adsorption_constants_823", adsorption_823)
    print("reaction_rates_648", reaction_rates(648.0, partial_pressures_bar))


if __name__ == "__main__":
    main()

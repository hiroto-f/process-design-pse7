"""Xu and Froment (1989) intrinsic kinetics for R1-R3."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from thermo.equilibrium import (
    equilibrium_constant_overall_reforming,
    equilibrium_constant_reforming,
    equilibrium_constant_wgs,
)


R_KJ_PER_MOL_K = 8.314462618e-3
PRESSURE_FLOOR_BAR = 1e-20


@dataclass(frozen=True)
class ArrheniusParameter:
    preexponential: float
    activation_energy_kj_per_mol: float

    def value(self, temperature_k: float) -> float:
        return self.preexponential * math.exp(
            -self.activation_energy_kj_per_mol / (R_KJ_PER_MOL_K * temperature_k)
        )


@dataclass(frozen=True)
class AdsorptionParameter:
    preexponential: float
    enthalpy_kj_per_mol: float

    def value(self, temperature_k: float) -> float:
        return self.preexponential * math.exp(
            -self.enthalpy_kj_per_mol / (R_KJ_PER_MOL_K * temperature_k)
        )


RATE_PARAMETERS = {
    "k1": ArrheniusParameter(4.225e15, 240.1),
    "k2": ArrheniusParameter(1.955e6, 67.13),
    "k3": ArrheniusParameter(1.020e15, 243.9),
}

ADSORPTION_PARAMETERS = {
    "CO": AdsorptionParameter(8.23e-5, -70.65),
    "H2": AdsorptionParameter(6.12e-9, -82.90),
    "CH4": AdsorptionParameter(6.65e-4, -38.28),
    "H2O": AdsorptionParameter(1.77e5, 88.68),
}

REFERENCE_ACTIVITY_FACTOR = 1.0
FRESH_CATALYST_ACTIVITY_FACTOR = 2.246


@dataclass(frozen=True)
class XuFromentRates:
    reforming: float
    water_gas_shift: float
    overall_reforming: float


def kinetic_constants(
    temperature_k: float,
    *,
    fresh_catalyst: bool = False,
) -> dict[str, float]:
    factor = (
        FRESH_CATALYST_ACTIVITY_FACTOR
        if fresh_catalyst
        else REFERENCE_ACTIVITY_FACTOR
    )
    return {
        name: factor * parameter.value(temperature_k)
        for name, parameter in RATE_PARAMETERS.items()
    }


def adsorption_constants(temperature_k: float) -> dict[str, float]:
    return {
        species: parameter.value(temperature_k)
        for species, parameter in ADSORPTION_PARAMETERS.items()
    }


def reaction_rates(
    temperature_k: float,
    partial_pressures_bar: Mapping[str, float],
    *,
    fresh_catalyst: bool = False,
) -> XuFromentRates:
    """Return Xu reaction rates in the paper's R1-R3 directions.

    Units follow the paper:
    - `r1`, `r3`: kmol / (kgcat h)
    - `r2`: kmol / (kgcat h)
    Partial pressures are in bar.
    """

    p_ch4 = max(float(partial_pressures_bar["CH4"]), PRESSURE_FLOOR_BAR)
    p_h2o = max(float(partial_pressures_bar["H2O"]), PRESSURE_FLOOR_BAR)
    p_co = max(float(partial_pressures_bar["CO"]), PRESSURE_FLOOR_BAR)
    p_h2 = max(float(partial_pressures_bar["H2"]), PRESSURE_FLOOR_BAR)
    p_co2 = max(float(partial_pressures_bar["CO2"]), PRESSURE_FLOOR_BAR)

    k = kinetic_constants(temperature_k, fresh_catalyst=fresh_catalyst)
    ads = adsorption_constants(temperature_k)
    k_eq_1 = equilibrium_constant_reforming(temperature_k)
    k_eq_2 = equilibrium_constant_wgs(temperature_k)
    k_eq_3 = equilibrium_constant_overall_reforming(temperature_k)

    denominator = (
        1.0
        + ads["CO"] * p_co
        + ads["H2"] * p_h2
        + ads["CH4"] * p_ch4
        + ads["H2O"] * p_h2o / p_h2
    ) ** 2

    r1 = (
        k["k1"]
        / (p_h2**2.5)
        * (p_ch4 * p_h2o - (p_h2**3) * p_co / k_eq_1)
        / denominator
    )
    r2 = (
        k["k2"]
        / p_h2
        * (p_co * p_h2o - p_h2 * p_co2 / k_eq_2)
        / denominator
    )
    r3 = (
        k["k3"]
        / (p_h2**3.5)
        * (p_ch4 * (p_h2o**2) - (p_h2**4) * p_co2 / k_eq_3)
        / denominator
    )

    return XuFromentRates(
        reforming=r1,
        water_gas_shift=r2,
        overall_reforming=r3,
    )


def species_rates(
    temperature_k: float,
    partial_pressures_bar: Mapping[str, float],
    *,
    fresh_catalyst: bool = False,
) -> dict[str, float]:
    """Return species source terms from Xu rates.

    Positive values mean net formation. Negative values mean net consumption.
    """

    rates = reaction_rates(
        temperature_k,
        partial_pressures_bar,
        fresh_catalyst=fresh_catalyst,
    )
    r1 = rates.reforming
    r2 = rates.water_gas_shift
    r3 = rates.overall_reforming

    return {
        "CH4": -(r1 + r3),
        "H2O": -(r1 + r2 + 2.0 * r3),
        "CO": r1 - r2,
        "H2": 3.0 * r1 + r2 + 4.0 * r3,
        "CO2": r2 + r3,
    }


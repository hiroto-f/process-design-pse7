"""Equilibrium constants for the Xu-Froment R1-R3 reaction set."""

from __future__ import annotations

import math


def equilibrium_constant_reforming(temperature_k: float) -> float:
    """R1: CH4 + H2O <-> CO + 3 H2."""

    return math.exp(-26830.0 / temperature_k + 30.114)


def equilibrium_constant_wgs(temperature_k: float) -> float:
    """R2: CO + H2O <-> CO2 + H2."""

    return math.exp(4400.0 / temperature_k - 4.036)


def equilibrium_constant_overall_reforming(temperature_k: float) -> float:
    """R3: CH4 + 2 H2O <-> CO2 + 4 H2."""

    return equilibrium_constant_reforming(
        temperature_k
    ) * equilibrium_constant_wgs(temperature_k)


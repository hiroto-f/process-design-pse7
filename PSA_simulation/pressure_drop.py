from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence


R = 8.31451


@dataclass(frozen=True)
class ErgunPressureProfile:
    """Pressure at packed-bed cell boundaries in physical z order."""

    pressures_kpa: tuple[float, ...]
    pressure_drop_kpa: float


def ergun_pressure_gradient_pa_per_m(
    pressure_pa: float,
    superficial_velocity_m_per_s: float,
    temperature_k: float,
    average_molar_mass_g_per_mol: float,
    viscosity_pa_s: float,
    bed_void_fraction: float,
    particle_diameter_m: float,
) -> float:
    """Return the positive Ergun pressure-loss magnitude per bed length."""
    if pressure_pa <= 0.0:
        raise ValueError("pressure_pa must be positive.")
    if temperature_k <= 0.0:
        raise ValueError("temperature_k must be positive.")
    if average_molar_mass_g_per_mol <= 0.0:
        raise ValueError("average_molar_mass_g_per_mol must be positive.")
    if viscosity_pa_s <= 0.0:
        raise ValueError("viscosity_pa_s must be positive.")
    if not 0.0 < bed_void_fraction < 1.0:
        raise ValueError("bed_void_fraction must be between zero and one.")
    if particle_diameter_m <= 0.0:
        raise ValueError("particle_diameter_m must be positive.")

    velocity = abs(superficial_velocity_m_per_s)
    density_kg_per_m3 = (
        pressure_pa
        * (average_molar_mass_g_per_mol / 1000.0)
        / (R * temperature_k)
    )
    one_minus_void = 1.0 - bed_void_fraction
    void_cubed = bed_void_fraction**3
    viscous = (
        150.0
        * one_minus_void**2
        / void_cubed
        * viscosity_pa_s
        * velocity
        / particle_diameter_m**2
    )
    inertial = (
        1.75
        * one_minus_void
        / void_cubed
        * density_kg_per_m3
        * velocity**2
        / particle_diameter_m
    )
    return viscous + inertial


def integrate_ergun_pressure_profile(
    reference_pressure_kpa: float,
    cell_velocities_m_per_s: Sequence[float],
    bed_length_m: float,
    temperature_k: float,
    average_molar_mass_g_per_mol: float,
    viscosity_pa_s: float,
    bed_void_fraction: float,
    particle_diameter_m: float,
    flow_direction: Literal["forward", "reverse"],
) -> ErgunPressureProfile:
    """Integrate Ergun loss over cells.

    ``forward`` uses the adsorption inlet at z=0 as the reference and pressure
    falls toward z=L. ``reverse`` uses the desorption product outlet at z=0 as
    the reference and integrates against the flow, so pressure rises toward the
    purge inlet at z=L.
    """
    if reference_pressure_kpa <= 0.0:
        raise ValueError("reference_pressure_kpa must be positive.")
    if bed_length_m <= 0.0:
        raise ValueError("bed_length_m must be positive.")
    if not cell_velocities_m_per_s:
        raise ValueError("cell_velocities_m_per_s must not be empty.")
    if flow_direction not in {"forward", "reverse"}:
        raise ValueError("flow_direction must be 'forward' or 'reverse'.")

    cell_length_m = bed_length_m / len(cell_velocities_m_per_s)
    pressure_pa = reference_pressure_kpa * 1000.0
    pressures_pa = [pressure_pa]
    sign = -1.0 if flow_direction == "forward" else 1.0

    for velocity in cell_velocities_m_per_s:
        gradient = ergun_pressure_gradient_pa_per_m(
            pressure_pa=pressure_pa,
            superficial_velocity_m_per_s=velocity,
            temperature_k=temperature_k,
            average_molar_mass_g_per_mol=average_molar_mass_g_per_mol,
            viscosity_pa_s=viscosity_pa_s,
            bed_void_fraction=bed_void_fraction,
            particle_diameter_m=particle_diameter_m,
        )
        pressure_pa += sign * gradient * cell_length_m
        if pressure_pa <= 0.0:
            raise ValueError(
                "Ergun pressure drop exceeds the available absolute pressure. "
                "Reduce velocity/bed length or increase particle size/pressure."
            )
        pressures_pa.append(pressure_pa)

    pressure_drop_kpa = abs(pressures_pa[-1] - pressures_pa[0]) / 1000.0
    return ErgunPressureProfile(
        pressures_kpa=tuple(value / 1000.0 for value in pressures_pa),
        pressure_drop_kpa=pressure_drop_kpa,
    )

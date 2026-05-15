from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdsorbentInput:
    particle_diameter_m: float
    bed_void_fraction: float
    macro_pore_void_fraction: float
    micro_pore_void_fraction: float
    macro_pore_radius_m: float
    micro_pore_radius_m: float
    bulk_density_kg_per_m3: float


@dataclass(frozen=True)
class ComponentInput:
    name: str
    langmuir_qmax_mol_per_g: float
    langmuir_b_per_kpa: float
    molar_mass_g_per_mol: float
    lennard_jones_epsilon_over_k_k: float
    lennard_jones_sigma_angstrom: float


@dataclass(frozen=True)
class TowerInput:
    adsorption_pressure_kpa: float
    desorption_pressure_kpa: float
    adsorption_temperature_c: float
    height_to_diameter_ratio: float
    adsorption_velocity_m_per_s: float
    desorption_velocity_m_per_s: float


@dataclass(frozen=True)
class FeedComponentInput:
    name: str
    flow_kmol_per_h: float


@dataclass(frozen=True)
class FeedInput:
    temperature_k: float | None
    pressure_kpa: float | None
    volume_flow_m3_per_h: float | None
    components_kmol_per_h: tuple[FeedComponentInput, ...]


@dataclass(frozen=True)
class SimulationInput:
    adsorbent: AdsorbentInput
    components: tuple[ComponentInput, ComponentInput]
    tower: TowerInput
    feed: FeedInput

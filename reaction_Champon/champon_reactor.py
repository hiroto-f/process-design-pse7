"""JSON-driven Champon methanation model for a cooled multitube reactor."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import setuptools  # Registers the distutils compatibility shim used by japanize_matplotlib.
import japanize_matplotlib
import matplotlib.pyplot as plt


GAS_CONSTANT_KJ_PER_KMOL_K = 8.314462618
GAS_CONSTANT_KJ_PER_MOL_K = GAS_CONSTANT_KJ_PER_KMOL_K / 1000.0
PRESSURE_FLOOR_BAR = 1e-12
PACKAGE_DIR = Path(__file__).parent
DEFAULT_INPUT_PATH = PACKAGE_DIR / "inputs" / "input.json"
DEFAULT_OUTPUT_PATH = PACKAGE_DIR / "outputs" / "summary.json"
DEFAULT_PROFILE_IMAGE_PATH = PACKAGE_DIR / "outputs" / "temperature_profile.png"
DEFAULT_RATE_PROFILE_IMAGE_PATH = PACKAGE_DIR / "outputs" / "reaction_rate_profile.png"
DEFAULT_POSITION_PROFILE_IMAGE_PATH = PACKAGE_DIR / "outputs" / "temperature_profile_z.png"
DEFAULT_POSITION_RATE_PROFILE_IMAGE_PATH = PACKAGE_DIR / "outputs" / "reaction_rate_profile_z.png"


@dataclass(frozen=True)
class ArrheniusConstant:
    preexponential_mol_per_gcat_min: float
    activation_energy_kj_per_mol: float

    def value_kmol_per_kgcat_h(self, temperature_k: float) -> float:
        value_mol_per_gcat_min = self.preexponential_mol_per_gcat_min * math.exp(
            -self.activation_energy_kj_per_mol
            / (GAS_CONSTANT_KJ_PER_MOL_K * temperature_k)
        )
        return value_mol_per_gcat_min * 60.0


@dataclass(frozen=True)
class AdsorptionConstant:
    preexponential_bar_inv: float
    heat_of_adsorption_kj_per_mol: float

    def value_bar_inv(self, temperature_k: float) -> float:
        return self.preexponential_bar_inv * math.exp(
            self.heat_of_adsorption_kj_per_mol
            / (GAS_CONSTANT_KJ_PER_MOL_K * temperature_k)
        )


@dataclass(frozen=True)
class ChamponKinetics:
    kinetic_constants: dict[str, ArrheniusConstant]
    adsorption_constants: dict[str, AdsorptionConstant]


@dataclass(frozen=True)
class Reaction:
    name: str
    equation: str
    stoichiometry: dict[str, float]


@dataclass(frozen=True)
class Feed:
    flows_kmol_per_h: dict[str, float]


@dataclass(frozen=True)
class ReactorConfig:
    temperature_k: float
    pressure_bar: float
    integration_steps: int

    def __post_init__(self) -> None:
        if self.temperature_k <= 0.0:
            raise ValueError("temperature_k must be positive")
        if self.pressure_bar <= 0.0:
            raise ValueError("pressure_bar must be positive")
        if self.integration_steps < 10:
            raise ValueError("integration_steps must be at least 10")


@dataclass(frozen=True)
class TemperatureSweep:
    start_k: int
    stop_k: int
    step_k: int


@dataclass(frozen=True)
class SizingConfig:
    target_conversion: float
    max_catalyst_mass_kg: float


@dataclass(frozen=True)
class Metrics:
    target_species: str
    product_species: str


@dataclass(frozen=True)
class CountercurrentCooling:
    coolant_inlet_temperature_k: float
    coolant_flow_kmol_per_h: float
    coolant_heat_capacity_kj_per_kmol_k: float
    heat_transfer_ua_kj_per_kgcat_h_k: float


@dataclass(frozen=True)
class ThermalConfig:
    enabled: bool
    species_heat_capacity_kj_per_kmol_k: dict[str, float]
    reaction_enthalpy_kj_per_kmol: dict[str, float]
    countercurrent_cooling: CountercurrentCooling


@dataclass(frozen=True)
class DesignCase:
    species: tuple[str, ...]
    reactions: tuple[Reaction, ...]
    kinetics: ChamponKinetics
    feed: Feed
    pressure_bar: float
    integration_steps: int
    tube_count: int
    tube_inner_diameter_m: float
    tube_length_m: float
    catalyst_bulk_density_kg_per_m3: float
    temperature_sweep: TemperatureSweep
    sizing: SizingConfig
    metrics: Metrics
    thermal: ThermalConfig


@dataclass(frozen=True)
class SimulationResult:
    catalyst_mass_kg: float
    catalyst_mass_per_tube_kg: float
    outlet_flows_kmol_per_h: dict[str, float]
    outlet_flows_per_tube_kmol_per_h: dict[str, float]
    target_conversion: float
    product_generation_kmol_per_h: float
    ch4_yield_on_co2_feed: float
    co_yield_on_co2_feed: float
    ch4_selectivity_on_converted_co2: float
    co_selectivity_on_converted_co2: float
    gas_outlet_temperature_k: float
    max_gas_temperature_k: float
    coolant_outlet_temperature_k: float
    cooling_duty_kj_per_h: float


@dataclass(frozen=True)
class SizingResult:
    temperature_k: float
    target_conversion: float
    reached_target: bool
    catalyst_mass_kg: float | None
    catalyst_mass_per_tube_kg: float | None
    search_limit_kg: float
    search_limit_per_tube_kg: float
    achieved_conversion: float
    outlet_flows_kmol_per_h: dict[str, float]
    outlet_flows_per_tube_kmol_per_h: dict[str, float]
    ch4_yield_on_co2_feed: float
    co_yield_on_co2_feed: float
    ch4_selectivity_on_converted_co2: float
    co_selectivity_on_converted_co2: float
    gas_outlet_temperature_k: float
    max_gas_temperature_k: float
    coolant_outlet_temperature_k: float
    cooling_duty_kj_per_h: float


@dataclass(frozen=True)
class TemperatureProfile:
    catalyst_mass_kg: tuple[float, ...]
    reactor_coordinate_m: tuple[float, ...]
    gas_temperature_k: tuple[float, ...]
    coolant_temperature_k: tuple[float, ...]
    reaction_rates_kmol_per_kgcat_h: dict[str, tuple[float, ...]]


def _as_mapping(raw: Any, label: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be a JSON object")
    return raw


def _as_float(raw: Any, label: str) -> float:
    if not isinstance(raw, (int, float)):
        raise ValueError(f"{label} must be numeric")
    return float(raw)


def _as_int(raw: Any, label: str) -> int:
    if not isinstance(raw, int):
        raise ValueError(f"{label} must be an integer")
    return raw


def _load_champon_kinetics(raw: Any, label: str) -> ChamponKinetics:
    data = _as_mapping(raw, label)
    kinetic_raw = _as_mapping(data["kinetic_constants"], f"{label}.kinetic_constants")
    adsorption_raw = _as_mapping(
        data["adsorption_constants"],
        f"{label}.adsorption_constants",
    )
    return ChamponKinetics(
        kinetic_constants={
            str(name): ArrheniusConstant(
                preexponential_mol_per_gcat_min=_as_float(
                    values["preexponential_mol_per_gcat_min"],
                    f"{label}.kinetic_constants.{name}.preexponential_mol_per_gcat_min",
                ),
                activation_energy_kj_per_mol=_as_float(
                    values["activation_energy_kj_per_mol"],
                    f"{label}.kinetic_constants.{name}.activation_energy_kj_per_mol",
                ),
            )
            for name, values in (
                (name, _as_mapping(value, f"{label}.kinetic_constants.{name}"))
                for name, value in kinetic_raw.items()
            )
        },
        adsorption_constants={
            str(species): AdsorptionConstant(
                preexponential_bar_inv=_as_float(
                    values["preexponential_bar_inv"],
                    f"{label}.adsorption_constants.{species}.preexponential_bar_inv",
                ),
                heat_of_adsorption_kj_per_mol=_as_float(
                    values["heat_of_adsorption_kj_per_mol"],
                    f"{label}.adsorption_constants.{species}.heat_of_adsorption_kj_per_mol",
                ),
            )
            for species, values in (
                (species, _as_mapping(value, f"{label}.adsorption_constants.{species}"))
                for species, value in adsorption_raw.items()
            )
        },
    )


def load_design_case(path: str | Path) -> DesignCase:
    """Load all reactor-design input data from JSON."""
    input_path = Path(path)
    data = _as_mapping(json.loads(input_path.read_text()), "root")

    species_raw = data["species"]
    if not isinstance(species_raw, list) or not all(
        isinstance(species, str) for species in species_raw
    ):
        raise ValueError("species must be a list of strings")
    species = tuple(species_raw)

    reactions_raw = data["reactions"]
    if not isinstance(reactions_raw, list) or not reactions_raw:
        raise ValueError("reactions must be a non-empty list")
    reactions: list[Reaction] = []
    for index, reaction_raw in enumerate(reactions_raw):
        label = f"reactions[{index}]"
        reaction_data = _as_mapping(reaction_raw, label)
        stoichiometry_raw = _as_mapping(
            reaction_data["stoichiometry"],
            f"{label}.stoichiometry",
        )
        reactions.append(
            Reaction(
                name=str(reaction_data["name"]),
                equation=str(reaction_data["equation"]),
                stoichiometry={
                    str(species_name): _as_float(
                        coefficient,
                        f"{label}.stoichiometry.{species_name}",
                    )
                    for species_name, coefficient in stoichiometry_raw.items()
                },
            )
        )

    kinetics = _load_champon_kinetics(data["kinetics"], "kinetics")
    feed_raw = _as_mapping(data["feed_kmol_per_h"], "feed_kmol_per_h")
    reactor_raw = _as_mapping(data["reactor"], "reactor")
    temperature_raw = _as_mapping(data["temperature_sweep_k"], "temperature_sweep_k")
    sizing_raw = _as_mapping(data["sizing"], "sizing")
    metrics_raw = _as_mapping(data["metrics"], "metrics")
    thermal_raw = _as_mapping(data["thermal"], "thermal")
    species_heat_capacity_raw = _as_mapping(
        thermal_raw["species_heat_capacity_kj_per_kmol_k"],
        "thermal.species_heat_capacity_kj_per_kmol_k",
    )
    reaction_enthalpy_raw = _as_mapping(
        thermal_raw["reaction_enthalpy_kj_per_kmol"],
        "thermal.reaction_enthalpy_kj_per_kmol",
    )
    cooling_raw = _as_mapping(
        thermal_raw["countercurrent_cooling"],
        "thermal.countercurrent_cooling",
    )

    design_case = DesignCase(
        species=species,
        reactions=tuple(reactions),
        kinetics=kinetics,
        feed=Feed(
            flows_kmol_per_h={
                str(species_name): _as_float(flow, f"feed_kmol_per_h.{species_name}")
                for species_name, flow in feed_raw.items()
            }
        ),
        pressure_bar=_as_float(reactor_raw["pressure_bar"], "reactor.pressure_bar"),
        integration_steps=_as_int(
            reactor_raw["integration_steps"],
            "reactor.integration_steps",
        ),
        tube_count=_as_int(reactor_raw["tube_count"], "reactor.tube_count"),
        tube_inner_diameter_m=_as_float(
            reactor_raw["tube_inner_diameter_m"],
            "reactor.tube_inner_diameter_m",
        ),
        tube_length_m=_as_float(
            reactor_raw["tube_length_m"],
            "reactor.tube_length_m",
        ),
        catalyst_bulk_density_kg_per_m3=_as_float(
            reactor_raw["catalyst_bulk_density_kg_per_m3"],
            "reactor.catalyst_bulk_density_kg_per_m3",
        ),
        temperature_sweep=TemperatureSweep(
            start_k=_as_int(temperature_raw["start"], "temperature_sweep_k.start"),
            stop_k=_as_int(temperature_raw["stop"], "temperature_sweep_k.stop"),
            step_k=_as_int(temperature_raw["step"], "temperature_sweep_k.step"),
        ),
        sizing=SizingConfig(
            target_conversion=_as_float(
                sizing_raw["target_conversion"],
                "sizing.target_conversion",
            ),
            max_catalyst_mass_kg=_as_float(
                sizing_raw["max_catalyst_mass_kg"],
                "sizing.max_catalyst_mass_kg",
            ),
        ),
        metrics=Metrics(
            target_species=str(metrics_raw["target_species"]),
            product_species=str(metrics_raw["product_species"]),
        ),
        thermal=ThermalConfig(
            enabled=bool(thermal_raw["enabled"]),
            species_heat_capacity_kj_per_kmol_k={
                str(species_name): _as_float(
                    heat_capacity,
                    f"thermal.species_heat_capacity_kj_per_kmol_k.{species_name}",
                )
                for species_name, heat_capacity in species_heat_capacity_raw.items()
            },
            reaction_enthalpy_kj_per_kmol={
                str(reaction_name): _as_float(
                    enthalpy,
                    f"thermal.reaction_enthalpy_kj_per_kmol.{reaction_name}",
                )
                for reaction_name, enthalpy in reaction_enthalpy_raw.items()
            },
            countercurrent_cooling=CountercurrentCooling(
                coolant_inlet_temperature_k=_as_float(
                    cooling_raw["coolant_inlet_temperature_k"],
                    "thermal.countercurrent_cooling.coolant_inlet_temperature_k",
                ),
                coolant_flow_kmol_per_h=_as_float(
                    cooling_raw["coolant_flow_kmol_per_h"],
                    "thermal.countercurrent_cooling.coolant_flow_kmol_per_h",
                ),
                coolant_heat_capacity_kj_per_kmol_k=_as_float(
                    cooling_raw["coolant_heat_capacity_kj_per_kmol_k"],
                    "thermal.countercurrent_cooling.coolant_heat_capacity_kj_per_kmol_k",
                ),
                heat_transfer_ua_kj_per_kgcat_h_k=_as_float(
                    cooling_raw["heat_transfer_ua_kj_per_kgcat_h_k"],
                    "thermal.countercurrent_cooling.heat_transfer_ua_kj_per_kgcat_h_k",
                ),
            ),
        ),
    )
    _validate_design_case(design_case)
    return design_case


def _validate_design_case(design_case: DesignCase) -> None:
    species = set(design_case.species)
    if not species:
        raise ValueError("species must not be empty")
    if set(design_case.feed.flows_kmol_per_h) != species:
        raise ValueError("feed_kmol_per_h keys must match species")
    for species_name, flow in design_case.feed.flows_kmol_per_h.items():
        if flow < 0.0:
            raise ValueError(f"{species_name} feed flow must be non-negative")
    if design_case.metrics.target_species not in species:
        raise ValueError("metrics.target_species must exist in species")
    if design_case.metrics.product_species not in species:
        raise ValueError("metrics.product_species must exist in species")
    if design_case.feed.flows_kmol_per_h[design_case.metrics.target_species] <= 0.0:
        raise ValueError("target species feed flow must be positive")
    for reaction in design_case.reactions:
        if set(reaction.stoichiometry) != species:
            raise ValueError(
                f"reaction {reaction.name!r} stoichiometry keys must match species"
            )
    expected_reaction_names = {
        "CO2 methanation",
        "reverse water-gas shift",
        "CO methanation",
    }
    if {reaction.name for reaction in design_case.reactions} != expected_reaction_names:
        raise ValueError("Champon model requires CO2 methanation, RWGS, and CO methanation")
    if set(design_case.kinetics.kinetic_constants) != expected_reaction_names:
        raise ValueError("kinetics.kinetic_constants must match the three Champon reactions")
    if set(design_case.kinetics.adsorption_constants) != {"CO", "H2O", "CO2", "H2"}:
        raise ValueError("kinetics.adsorption_constants must define CO, H2O, CO2, and H2")
    if not 0.0 < design_case.sizing.target_conversion < 1.0:
        raise ValueError("sizing.target_conversion must lie between 0 and 1")
    if design_case.sizing.max_catalyst_mass_kg <= 0.0:
        raise ValueError("sizing.max_catalyst_mass_kg must be positive")
    if design_case.tube_count <= 0:
        raise ValueError("reactor.tube_count must be positive")
    if design_case.tube_inner_diameter_m <= 0.0:
        raise ValueError("reactor.tube_inner_diameter_m must be positive")
    if design_case.tube_length_m <= 0.0:
        raise ValueError("reactor.tube_length_m must be positive")
    if design_case.catalyst_bulk_density_kg_per_m3 <= 0.0:
        raise ValueError("reactor.catalyst_bulk_density_kg_per_m3 must be positive")
    if design_case.temperature_sweep.step_k <= 0:
        raise ValueError("temperature_sweep_k.step must be positive")
    if not 623 <= design_case.temperature_sweep.start_k <= 723:
        raise ValueError("temperature_sweep_k.start must be within Champon's 623-723 K range")
    if not 623 <= design_case.temperature_sweep.stop_k <= 723:
        raise ValueError("temperature_sweep_k.stop must be within Champon's 623-723 K range")
    if set(design_case.thermal.species_heat_capacity_kj_per_kmol_k) != species:
        raise ValueError("thermal heat-capacity keys must match species")
    if set(design_case.thermal.reaction_enthalpy_kj_per_kmol) != {
        reaction.name for reaction in design_case.reactions
    }:
        raise ValueError("thermal reaction-enthalpy keys must match reaction names")
    for species_name, heat_capacity in (
        design_case.thermal.species_heat_capacity_kj_per_kmol_k.items()
    ):
        if heat_capacity <= 0.0:
            raise ValueError(f"{species_name} heat capacity must be positive")
    cooling = design_case.thermal.countercurrent_cooling
    if cooling.coolant_flow_kmol_per_h <= 0.0:
        raise ValueError("coolant flow must be positive")
    if cooling.coolant_heat_capacity_kj_per_kmol_k <= 0.0:
        raise ValueError("coolant heat capacity must be positive")
    if cooling.heat_transfer_ua_kj_per_kgcat_h_k <= 0.0:
        raise ValueError("heat-transfer UA must be positive")


def partial_pressures(
    flows_kmol_per_h: dict[str, float],
    total_pressure_bar: float,
) -> dict[str, float]:
    total_flow = sum(max(flow, 0.0) for flow in flows_kmol_per_h.values())
    if total_flow <= 0.0:
        raise ValueError("total flow must stay positive")
    return {
        species: max(flow, 0.0) / total_flow * total_pressure_bar
        for species, flow in flows_kmol_per_h.items()
    }


def _scaled_flows(flows_kmol_per_h: dict[str, float], factor: float) -> dict[str, float]:
    return {species: flow * factor for species, flow in flows_kmol_per_h.items()}


def representative_tube_feed(design_case: DesignCase) -> dict[str, float]:
    return _scaled_flows(design_case.feed.flows_kmol_per_h, 1.0 / design_case.tube_count)


def representative_tube_coolant_flow_kmol_per_h(design_case: DesignCase) -> float:
    return (
        design_case.thermal.countercurrent_cooling.coolant_flow_kmol_per_h
        / design_case.tube_count
    )


@dataclass(frozen=True)
class ShomateCoefficients:
    a: float
    b: float
    c: float
    d: float
    e: float
    f: float
    g: float
    h: float

    def standard_gibbs_energy_kj_per_mol(self, temperature_k: float) -> float:
        t = temperature_k / 1000.0
        enthalpy_increment = (
            self.a * t
            + self.b * t**2 / 2.0
            + self.c * t**3 / 3.0
            + self.d * t**4 / 4.0
            - self.e / t
            + self.f
            - self.h
        )
        entropy_j_per_mol_k = (
            self.a * math.log(t)
            + self.b * t
            + self.c * t**2 / 2.0
            + self.d * t**3 / 3.0
            - self.e / (2.0 * t**2)
            + self.g
        )
        return self.h + enthalpy_increment - temperature_k * entropy_j_per_mol_k / 1000.0


SHOMATE_COEFFICIENTS = {
    "CO2": ShomateCoefficients(
        24.99735, 55.18696, -33.69137, 7.948387, -0.136638, -403.6075, 228.2431, -393.5224
    ),
    "H2": ShomateCoefficients(
        33.066178, -11.363417, 11.432816, -2.772874, -0.158558, -9.980797, 172.707974, 0.0
    ),
    "CH4": ShomateCoefficients(
        -0.703029, 108.4773, -42.52157, 5.862788, 0.678565, -76.84376, 158.7163, -74.87310
    ),
    "H2O": ShomateCoefficients(
        30.09200, 6.832514, 6.793435, -2.534480, 0.082139, -250.8810, 223.3967, -241.8264
    ),
    "CO": ShomateCoefficients(
        25.56759, 6.096130, 4.054656, -2.671301, 0.131021, -118.0089, 227.3665, -110.5271
    ),
}


def equilibrium_constant(
    stoichiometry: dict[str, float],
    temperature_k: float,
) -> float:
    delta_g_kj_per_mol = sum(
        coefficient
        * SHOMATE_COEFFICIENTS[species].standard_gibbs_energy_kj_per_mol(temperature_k)
        for species, coefficient in stoichiometry.items()
    )
    return math.exp(-delta_g_kj_per_mol / (GAS_CONSTANT_KJ_PER_MOL_K * temperature_k))


def reaction_rate_kmol_per_kgcat_h(
    flows_kmol_per_h: dict[str, float],
    config: ReactorConfig,
    reaction: Reaction,
    kinetics: ChamponKinetics,
) -> float:
    """Return one Champon et al. reaction rate."""
    pressures = partial_pressures(flows_kmol_per_h, config.pressure_bar)
    adsorption = {
        species: constant.value_bar_inv(config.temperature_k)
        for species, constant in kinetics.adsorption_constants.items()
    }
    denominator = 1.0 + sum(
        adsorption[species] * pressures[species]
        for species in ("CO2", "H2", "H2O", "CO")
    )
    k = kinetics.kinetic_constants[reaction.name].value_kmol_per_kgcat_h(
        config.temperature_k
    )
    keq = equilibrium_constant(reaction.stoichiometry, config.temperature_k)

    if reaction.name == "CO2 methanation":
        driving_force = 1.0 - (
            pressures["CH4"] * pressures["H2O"] ** 2
            / max(
                pressures["H2"] ** 4 * pressures["CO2"] * keq,
                PRESSURE_FLOOR_BAR,
            )
        )
        numerator = (
            k
            * adsorption["H2"]
            * adsorption["CO2"]
            * pressures["H2"]
            * pressures["CO2"]
            * driving_force
        )
        return numerator / denominator**2

    if reaction.name == "reverse water-gas shift":
        driving_force = 1.0 - (
            pressures["CO"] * pressures["H2O"]
            / max(pressures["H2"] * pressures["CO2"] * keq, PRESSURE_FLOOR_BAR)
        )
        numerator = k * adsorption["CO2"] * pressures["CO2"] * driving_force
        return numerator / denominator

    if reaction.name == "CO methanation":
        driving_force = 1.0 - (
            pressures["CH4"] * pressures["H2O"]
            / max(pressures["H2"] ** 3 * pressures["CO"] * keq, PRESSURE_FLOOR_BAR)
        )
        numerator = (
            k
            * adsorption["H2"]
            * adsorption["CO"]
            * pressures["H2"]
            * pressures["CO"]
            * driving_force
        )
        return numerator / denominator**2

    raise ValueError(f"unsupported Champon reaction: {reaction.name}")


def reaction_rates_kmol_per_kgcat_h(
    flows_kmol_per_h: dict[str, float],
    config: ReactorConfig,
    reactions: tuple[Reaction, ...],
    kinetics: ChamponKinetics,
) -> dict[str, float]:
    return {
        reaction.name: reaction_rate_kmol_per_kgcat_h(
            flows_kmol_per_h,
            config,
            reaction,
            kinetics,
        )
        for reaction in reactions
    }


def _derivatives(
    flows_kmol_per_h: dict[str, float],
    config: ReactorConfig,
    design_case: DesignCase,
) -> dict[str, float]:
    rates = reaction_rates_kmol_per_kgcat_h(
        flows_kmol_per_h,
        config,
        design_case.reactions,
        design_case.kinetics,
    )
    return {
        species: sum(
            reaction.stoichiometry[species] * rates[reaction.name]
            for reaction in design_case.reactions
        )
        for species in design_case.species
    }


def _heat_capacity_flow_kj_per_h_k(
    flows_kmol_per_h: dict[str, float],
    heat_capacities_kj_per_kmol_k: dict[str, float],
) -> float:
    heat_capacity_flow = sum(
        max(flows_kmol_per_h[species], 0.0) * heat_capacities_kj_per_kmol_k[species]
        for species in flows_kmol_per_h
    )
    if heat_capacity_flow <= 0.0:
        raise ValueError("gas heat-capacity flow must stay positive")
    return heat_capacity_flow


def _thermal_derivatives(
    flows_kmol_per_h: dict[str, float],
    gas_temperature_k: float,
    coolant_temperature_k: float,
    config: ReactorConfig,
    design_case: DesignCase,
) -> tuple[dict[str, float], float, float]:
    thermal_config = design_case.thermal
    rates = reaction_rates_kmol_per_kgcat_h(
        flows_kmol_per_h,
        ReactorConfig(
            temperature_k=gas_temperature_k,
            pressure_bar=config.pressure_bar,
            integration_steps=config.integration_steps,
        ),
        design_case.reactions,
        design_case.kinetics,
    )
    flow_derivatives = {
        species: sum(
            reaction.stoichiometry[species] * rates[reaction.name]
            for reaction in design_case.reactions
        )
        for species in design_case.species
    }
    reaction_heat_release_kj_per_kgcat_h = sum(
        -thermal_config.reaction_enthalpy_kj_per_kmol[reaction.name]
        * rates[reaction.name]
        for reaction in design_case.reactions
    )
    heat_transfer_kj_per_kgcat_h = (
        thermal_config.countercurrent_cooling.heat_transfer_ua_kj_per_kgcat_h_k
        * (gas_temperature_k - coolant_temperature_k)
    )
    gas_heat_capacity_flow = _heat_capacity_flow_kj_per_h_k(
        flows_kmol_per_h,
        thermal_config.species_heat_capacity_kj_per_kmol_k,
    )
    coolant_heat_capacity_flow = (
        representative_tube_coolant_flow_kmol_per_h(design_case)
        * thermal_config.countercurrent_cooling.coolant_heat_capacity_kj_per_kmol_k
    )
    gas_temperature_derivative = (
        reaction_heat_release_kj_per_kgcat_h - heat_transfer_kj_per_kgcat_h
    ) / gas_heat_capacity_flow
    coolant_temperature_derivative = -heat_transfer_kj_per_kgcat_h / coolant_heat_capacity_flow
    return flow_derivatives, gas_temperature_derivative, coolant_temperature_derivative


def _advance_euler(
    flows_kmol_per_h: dict[str, float],
    step_mass_kg: float,
    config: ReactorConfig,
    design_case: DesignCase,
) -> dict[str, float]:
    derivatives = _derivatives(flows_kmol_per_h, config, design_case)
    return {
        species: max(flows_kmol_per_h[species] + derivatives[species] * step_mass_kg, 0.0)
        for species in design_case.species
    }


def _advance_thermal_euler(
    flows_kmol_per_h: dict[str, float],
    gas_temperature_k: float,
    coolant_temperature_k: float,
    step_mass_kg: float,
    config: ReactorConfig,
    design_case: DesignCase,
) -> tuple[dict[str, float], float, float]:
    flow_derivatives, gas_temperature_derivative, coolant_temperature_derivative = (
        _thermal_derivatives(
            flows_kmol_per_h,
            gas_temperature_k,
            coolant_temperature_k,
            config,
            design_case,
        )
    )
    next_flows = {
        species: max(flows_kmol_per_h[species] + flow_derivatives[species] * step_mass_kg, 0.0)
        for species in design_case.species
    }
    return (
        next_flows,
        gas_temperature_k + gas_temperature_derivative * step_mass_kg,
        coolant_temperature_k + coolant_temperature_derivative * step_mass_kg,
    )


def _stable_thermal_step_mass(
    flows_kmol_per_h: dict[str, float],
    gas_temperature_k: float,
    coolant_temperature_k: float,
    nominal_step_mass_kg: float,
    config: ReactorConfig,
    design_case: DesignCase,
) -> float:
    flow_derivatives, gas_temperature_derivative, coolant_temperature_derivative = (
        _thermal_derivatives(
            flows_kmol_per_h,
            gas_temperature_k,
            coolant_temperature_k,
            config,
            design_case,
        )
    )
    step_mass_kg = nominal_step_mass_kg
    for species, derivative in flow_derivatives.items():
        flow = flows_kmol_per_h[species]
        if derivative < 0.0 and flow > 0.0:
            step_mass_kg = min(step_mass_kg, 0.05 * flow / abs(derivative))
    for temperature_derivative in (gas_temperature_derivative, coolant_temperature_derivative):
        if temperature_derivative != 0.0:
            step_mass_kg = min(step_mass_kg, 1.0 / abs(temperature_derivative))
    return max(step_mass_kg, nominal_step_mass_kg * 1.0e-6)


def catalyst_mass_per_length_kg_per_m(design_case: DesignCase) -> float:
    tube_cross_section_area_m2 = math.pi * design_case.tube_inner_diameter_m**2 / 4.0
    return design_case.catalyst_bulk_density_kg_per_m3 * tube_cross_section_area_m2


def available_catalyst_mass_per_tube_kg(design_case: DesignCase) -> float:
    return catalyst_mass_per_length_kg_per_m(design_case) * design_case.tube_length_m


def available_total_catalyst_mass_kg(design_case: DesignCase) -> float:
    return available_catalyst_mass_per_tube_kg(design_case) * design_case.tube_count


def _integrate_countercurrent_profile(
    design_case: DesignCase,
    config: ReactorConfig,
    catalyst_mass_kg: float,
    coolant_temperature_at_gas_inlet_k: float,
) -> tuple[dict[str, float], float, float, float, TemperatureProfile]:
    flows = representative_tube_feed(design_case)
    gas_temperature_k = config.temperature_k
    coolant_temperature_k = coolant_temperature_at_gas_inlet_k
    max_gas_temperature_k = gas_temperature_k
    catalyst_mass_profile = [0.0]
    reactor_coordinate_profile = [0.0]
    gas_temperature_profile = [gas_temperature_k]
    coolant_temperature_profile = [coolant_temperature_k]
    reaction_rate_profile = {
        reaction.name: [
            reaction_rate_kmol_per_kgcat_h(
                flows,
                ReactorConfig(
                    temperature_k=gas_temperature_k,
                    pressure_bar=config.pressure_bar,
                    integration_steps=config.integration_steps,
                ),
                reaction,
                design_case.kinetics,
            )
        ]
        for reaction in design_case.reactions
    }
    if catalyst_mass_kg <= 0.0:
        return (
            flows,
            gas_temperature_k,
            coolant_temperature_k,
            max_gas_temperature_k,
            TemperatureProfile(
                catalyst_mass_kg=tuple(catalyst_mass_profile),
                reactor_coordinate_m=tuple(reactor_coordinate_profile),
                gas_temperature_k=tuple(gas_temperature_profile),
                coolant_temperature_k=tuple(coolant_temperature_profile),
                reaction_rates_kmol_per_kgcat_h={
                    name: tuple(values) for name, values in reaction_rate_profile.items()
                },
            ),
        )

    step_mass = catalyst_mass_kg / config.integration_steps
    mass_per_length_kg_per_m = catalyst_mass_per_length_kg_per_m(design_case)
    current_catalyst_mass_kg = 0.0
    for step_index in range(config.integration_steps):
        remaining_step_mass = step_mass
        while remaining_step_mass > 0.0:
            current_step_mass = min(
                remaining_step_mass,
                _stable_thermal_step_mass(
                    flows,
                    gas_temperature_k,
                    coolant_temperature_k,
                    remaining_step_mass,
                    config,
                    design_case,
                ),
            )
            flows, gas_temperature_k, coolant_temperature_k = _advance_thermal_euler(
                flows,
                gas_temperature_k,
                coolant_temperature_k,
                current_step_mass,
                config,
                design_case,
            )
            max_gas_temperature_k = max(max_gas_temperature_k, gas_temperature_k)
            remaining_step_mass -= current_step_mass
            current_catalyst_mass_kg += current_step_mass
            catalyst_mass_profile.append(current_catalyst_mass_kg)
            reactor_coordinate_profile.append(
                current_catalyst_mass_kg / mass_per_length_kg_per_m
            )
            gas_temperature_profile.append(gas_temperature_k)
            coolant_temperature_profile.append(coolant_temperature_k)
            current_rates = reaction_rates_kmol_per_kgcat_h(
                flows,
                ReactorConfig(
                    temperature_k=gas_temperature_k,
                    pressure_bar=config.pressure_bar,
                    integration_steps=config.integration_steps,
                ),
                design_case.reactions,
                design_case.kinetics,
            )
            for reaction_name, rate in current_rates.items():
                reaction_rate_profile[reaction_name].append(rate)
    return (
        flows,
        gas_temperature_k,
        coolant_temperature_k,
        max_gas_temperature_k,
        TemperatureProfile(
            catalyst_mass_kg=tuple(catalyst_mass_profile),
            reactor_coordinate_m=tuple(reactor_coordinate_profile),
            gas_temperature_k=tuple(gas_temperature_profile),
            coolant_temperature_k=tuple(coolant_temperature_profile),
            reaction_rates_kmol_per_kgcat_h={
                name: tuple(values) for name, values in reaction_rate_profile.items()
            },
        ),
    )


def _solve_countercurrent_profile(
    design_case: DesignCase,
    config: ReactorConfig,
    catalyst_mass_kg: float,
) -> tuple[dict[str, float], float, float, float, TemperatureProfile]:
    cooling = design_case.thermal.countercurrent_cooling
    target_coolant_inlet_k = cooling.coolant_inlet_temperature_k
    if catalyst_mass_kg <= 0.0:
        return (
            representative_tube_feed(design_case),
            config.temperature_k,
            target_coolant_inlet_k,
            config.temperature_k,
                TemperatureProfile(
                    catalyst_mass_kg=(0.0,),
                    reactor_coordinate_m=(0.0,),
                    gas_temperature_k=(config.temperature_k,),
                coolant_temperature_k=(target_coolant_inlet_k,),
                reaction_rates_kmol_per_kgcat_h={
                    reaction.name: (
                        reaction_rate_kmol_per_kgcat_h(
                            representative_tube_feed(design_case),
                            config,
                            reaction,
                            design_case.kinetics,
                        ),
                    )
                    for reaction in design_case.reactions
                },
            ),
        )

    def residual(coolant_temperature_at_gas_inlet_k: float) -> tuple[
        float,
        tuple[dict[str, float], float, float, float, TemperatureProfile],
    ]:
        profile = _integrate_countercurrent_profile(
            design_case,
            config,
            catalyst_mass_kg,
            coolant_temperature_at_gas_inlet_k,
        )
        return profile[2] - target_coolant_inlet_k, profile

    lower = target_coolant_inlet_k
    upper = max(config.temperature_k + 200.0, target_coolant_inlet_k + 200.0)
    lower_residual, _ = residual(lower)
    upper_residual, upper_profile = residual(upper)
    while lower_residual * upper_residual > 0.0:
        upper += 200.0
        upper_residual, upper_profile = residual(upper)
        if upper > target_coolant_inlet_k + 5000.0:
            raise RuntimeError("could not bracket the countercurrent coolant outlet temperature")

    best_profile = upper_profile
    best_coolant_outlet_temperature_k = upper
    for _ in range(40):
        midpoint = 0.5 * (lower + upper)
        midpoint_residual, midpoint_profile = residual(midpoint)
        best_profile = midpoint_profile
        best_coolant_outlet_temperature_k = midpoint
        if abs(midpoint_residual) <= 1.0e-6:
            break
        if lower_residual * midpoint_residual <= 0.0:
            upper = midpoint
            upper_residual = midpoint_residual
        else:
            lower = midpoint
            lower_residual = midpoint_residual
    flows, gas_outlet_temperature_k, _, max_gas_temperature_k, temperature_profile = (
        best_profile
    )
    return (
        flows,
        gas_outlet_temperature_k,
        best_coolant_outlet_temperature_k,
        max_gas_temperature_k,
        temperature_profile,
    )


def simulate_fixed_bed(
    design_case: DesignCase,
    config: ReactorConfig,
    catalyst_mass_kg: float,
) -> SimulationResult:
    """Integrate the packed-bed balance over catalyst mass."""
    if catalyst_mass_kg < 0.0:
        raise ValueError("catalyst_mass_kg must be non-negative")

    catalyst_mass_per_tube_kg = catalyst_mass_kg / design_case.tube_count
    if design_case.thermal.enabled:
        (
            flows,
            gas_outlet_temperature_k,
            coolant_outlet_temperature_k,
            max_gas_temperature_k,
            _,
        ) = _solve_countercurrent_profile(design_case, config, catalyst_mass_per_tube_kg)
    else:
        flows = representative_tube_feed(design_case)
        if catalyst_mass_per_tube_kg > 0.0:
            step_mass = catalyst_mass_per_tube_kg / config.integration_steps
            for _ in range(config.integration_steps):
                flows = _advance_euler(flows, step_mass, config, design_case)
        gas_outlet_temperature_k = config.temperature_k
        coolant_outlet_temperature_k = (
            design_case.thermal.countercurrent_cooling.coolant_inlet_temperature_k
        )
        max_gas_temperature_k = config.temperature_k

    target_species = design_case.metrics.target_species
    product_species = design_case.metrics.product_species
    inlet_target_flow = representative_tube_feed(design_case)[target_species]
    inlet_product_flow = representative_tube_feed(design_case)[product_species]
    conversion = 1.0 - flows[target_species] / inlet_target_flow
    total_outlet_flows = _scaled_flows(flows, design_case.tube_count)
    converted_target_flow = max(
        design_case.feed.flows_kmol_per_h[target_species] - total_outlet_flows[target_species],
        0.0,
    )
    ch4_generation = max(
        total_outlet_flows["CH4"] - design_case.feed.flows_kmol_per_h["CH4"],
        0.0,
    )
    co_generation = max(
        total_outlet_flows["CO"] - design_case.feed.flows_kmol_per_h["CO"],
        0.0,
    )
    return SimulationResult(
        catalyst_mass_kg=catalyst_mass_kg,
        catalyst_mass_per_tube_kg=catalyst_mass_per_tube_kg,
        outlet_flows_kmol_per_h=total_outlet_flows,
        outlet_flows_per_tube_kmol_per_h=flows,
        target_conversion=max(0.0, min(conversion, 1.0)),
        product_generation_kmol_per_h=ch4_generation,
        ch4_yield_on_co2_feed=ch4_generation
        / design_case.feed.flows_kmol_per_h[target_species],
        co_yield_on_co2_feed=co_generation
        / design_case.feed.flows_kmol_per_h[target_species],
        ch4_selectivity_on_converted_co2=(
            ch4_generation / converted_target_flow if converted_target_flow > 0.0 else 0.0
        ),
        co_selectivity_on_converted_co2=(
            co_generation / converted_target_flow if converted_target_flow > 0.0 else 0.0
        ),
        gas_outlet_temperature_k=gas_outlet_temperature_k,
        max_gas_temperature_k=max_gas_temperature_k,
        coolant_outlet_temperature_k=coolant_outlet_temperature_k,
        cooling_duty_kj_per_h=(
            representative_tube_coolant_flow_kmol_per_h(design_case)
            * design_case.thermal.countercurrent_cooling.coolant_heat_capacity_kj_per_kmol_k
            * (
                coolant_outlet_temperature_k
                - design_case.thermal.countercurrent_cooling.coolant_inlet_temperature_k
            )
        )
        * design_case.tube_count,
    )


def evaluate_fixed_geometry(
    design_case: DesignCase,
    config: ReactorConfig,
) -> SizingResult:
    """Evaluate the geometry-defined catalyst inventory without resizing the reactor."""
    catalyst_mass_kg = available_total_catalyst_mass_kg(design_case)
    result = simulate_fixed_bed(design_case, config, catalyst_mass_kg)
    return SizingResult(
        temperature_k=config.temperature_k,
        target_conversion=design_case.sizing.target_conversion,
        reached_target=result.target_conversion >= design_case.sizing.target_conversion,
        catalyst_mass_kg=result.catalyst_mass_kg,
        catalyst_mass_per_tube_kg=result.catalyst_mass_per_tube_kg,
        search_limit_kg=catalyst_mass_kg,
        search_limit_per_tube_kg=result.catalyst_mass_per_tube_kg,
        achieved_conversion=result.target_conversion,
        outlet_flows_kmol_per_h=result.outlet_flows_kmol_per_h,
        outlet_flows_per_tube_kmol_per_h=result.outlet_flows_per_tube_kmol_per_h,
        ch4_yield_on_co2_feed=result.ch4_yield_on_co2_feed,
        co_yield_on_co2_feed=result.co_yield_on_co2_feed,
        ch4_selectivity_on_converted_co2=result.ch4_selectivity_on_converted_co2,
        co_selectivity_on_converted_co2=result.co_selectivity_on_converted_co2,
        gas_outlet_temperature_k=result.gas_outlet_temperature_k,
        max_gas_temperature_k=result.max_gas_temperature_k,
        coolant_outlet_temperature_k=result.coolant_outlet_temperature_k,
        cooling_duty_kj_per_h=result.cooling_duty_kj_per_h,
    )


def temperature_grid(sweep: TemperatureSweep) -> Iterable[int]:
    current = sweep.start_k
    while current <= sweep.stop_k:
        yield current
        current += sweep.step_k


def format_sizing_table(results: Iterable[SizingResult], target_species: str) -> str:
    lines = [
        f"T_in [K] | target X_{target_species} | total catalyst [kg] | "
        f"achieved X_{target_species} | T_g,out [K] | T_g,max [K] | "
        f"T_c,out [K] | Q_removed [kJ/h] | status",
        "-" * 139,
    ]
    for result in results:
        mass = (
            f"{result.catalyst_mass_kg:.6g}"
            if result.catalyst_mass_kg is not None
            else f">{result.search_limit_kg:.6g}"
        )
        status = "target reached" if result.reached_target else "not reached"
        lines.append(
            f"{result.temperature_k:5.1f} | "
            f"{result.target_conversion:14.3f} | "
            f"{mass:18} | "
            f"{result.achieved_conversion:16.6g} | "
            f"{result.gas_outlet_temperature_k:11.3f} | "
            f"{result.max_gas_temperature_k:11.3f} | "
            f"{result.coolant_outlet_temperature_k:11.3f} | "
            f"{result.cooling_duty_kj_per_h:16.6g} | "
            f"{status}"
        )
    return "\n".join(lines)


def build_summary(
    design_case: DesignCase,
    results: Iterable[SizingResult],
) -> dict[str, Any]:
    cooling = design_case.thermal.countercurrent_cooling
    return {
        "reactions": [
            {
                "name": reaction.name,
                "equation": reaction.equation,
            }
            for reaction in design_case.reactions
        ],
        "basis": {
            "model": "non-isothermal multitube packed-bed reactor with countercurrent cooling",
            "kinetic_model": "Champon et al. (2019)",
            "pressure_bar": design_case.pressure_bar,
            "tube_count": design_case.tube_count,
            "tube_inner_diameter_m": design_case.tube_inner_diameter_m,
            "tube_length_m": design_case.tube_length_m,
            "catalyst_bulk_density_kg_per_m3": design_case.catalyst_bulk_density_kg_per_m3,
            "available_catalyst_mass_per_tube_kg": available_catalyst_mass_per_tube_kg(
                design_case
            ),
            "available_total_catalyst_mass_kg": available_total_catalyst_mass_kg(
                design_case
            ),
            "total_feed_kmol_per_h": design_case.feed.flows_kmol_per_h,
            "feed_per_tube_kmol_per_h": representative_tube_feed(design_case),
            "target_species": design_case.metrics.target_species,
            "product_species": design_case.metrics.product_species,
        },
        "cooling": {
            "coolant_inlet_temperature_k": cooling.coolant_inlet_temperature_k,
            "total_coolant_flow_kmol_per_h": cooling.coolant_flow_kmol_per_h,
            "coolant_flow_per_tube_kmol_per_h": representative_tube_coolant_flow_kmol_per_h(
                design_case
            ),
            "coolant_heat_capacity_kj_per_kmol_k": cooling.coolant_heat_capacity_kj_per_kmol_k,
            "heat_transfer_ua_kj_per_kgcat_h_k": cooling.heat_transfer_ua_kj_per_kgcat_h_k,
        },
        "results": [
            {
                "inlet_temperature_k": result.temperature_k,
                "target_conversion": result.target_conversion,
                "reached_target": result.reached_target,
                "total_catalyst_mass_kg": result.catalyst_mass_kg,
                "catalyst_mass_per_tube_kg": result.catalyst_mass_per_tube_kg,
                "total_search_limit_kg": result.search_limit_kg,
                "search_limit_per_tube_kg": result.search_limit_per_tube_kg,
                "achieved_conversion": result.achieved_conversion,
                "ch4_yield_on_co2_feed": result.ch4_yield_on_co2_feed,
                "co_yield_on_co2_feed": result.co_yield_on_co2_feed,
                "ch4_selectivity_on_converted_co2": result.ch4_selectivity_on_converted_co2,
                "co_selectivity_on_converted_co2": result.co_selectivity_on_converted_co2,
                "total_outlet_flows_kmol_per_h": result.outlet_flows_kmol_per_h,
                "outlet_flows_per_tube_kmol_per_h": result.outlet_flows_per_tube_kmol_per_h,
                "gas_outlet_temperature_k": result.gas_outlet_temperature_k,
                "max_gas_temperature_k": result.max_gas_temperature_k,
                "coolant_outlet_temperature_k": result.coolant_outlet_temperature_k,
                "cooling_duty_kj_per_h": result.cooling_duty_kj_per_h,
            }
            for result in results
        ],
    }


def write_summary(path: str | Path, summary: dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2) + "\n")


def temperature_profile_for_result(
    design_case: DesignCase,
    result: SizingResult,
) -> TemperatureProfile:
    catalyst_mass_per_tube_kg = (
        result.catalyst_mass_per_tube_kg
        if result.catalyst_mass_per_tube_kg is not None
        else result.search_limit_per_tube_kg
    )
    maximum_catalyst_mass_per_tube_kg = (
        catalyst_mass_per_length_kg_per_m(design_case) * design_case.tube_length_m
    )
    if catalyst_mass_per_tube_kg > maximum_catalyst_mass_per_tube_kg:
        raise ValueError("required catalyst mass exceeds the available tube length")
    _, _, _, _, profile = _solve_countercurrent_profile(
        design_case,
        ReactorConfig(
            temperature_k=result.temperature_k,
            pressure_bar=design_case.pressure_bar,
            integration_steps=design_case.integration_steps,
        ),
        catalyst_mass_per_tube_kg,
    )
    return profile


def temperature_profile_for_full_bed(
    design_case: DesignCase,
    temperature_k: float,
) -> TemperatureProfile:
    """Return a full-length reactor profile using the geometry-defined catalyst inventory."""
    _, _, _, _, profile = _solve_countercurrent_profile(
        design_case,
        ReactorConfig(
            temperature_k=temperature_k,
            pressure_bar=design_case.pressure_bar,
            integration_steps=design_case.integration_steps,
        ),
        available_catalyst_mass_per_tube_kg(design_case),
    )
    return profile


def validate_profile_temperature_range(profile: TemperatureProfile) -> None:
    if min(profile.gas_temperature_k) < 623.0 or max(profile.gas_temperature_k) > 723.0:
        raise ValueError("gas-temperature profile must stay within Champon's 623-723 K range")


def validate_nonincreasing_gas_temperature_profile(profile: TemperatureProfile) -> None:
    if any(
        profile.gas_temperature_k[index + 1] > profile.gas_temperature_k[index] + 1.0e-9
        for index in range(len(profile.gas_temperature_k) - 1)
    ):
        raise ValueError("gas-temperature profile must be non-increasing")


def write_temperature_profile_image(
    path: str | Path,
    profile: TemperatureProfile,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    figure, axes = plt.subplots(figsize=(9.6, 5.4), dpi=100)
    axes.plot(
        profile.catalyst_mass_kg,
        profile.gas_temperature_k,
        color="#c43c30",
        linewidth=2.0,
        label="管内ガス温度",
    )
    axes.plot(
        profile.catalyst_mass_kg,
        profile.coolant_temperature_k,
        color="#2070b2",
        linewidth=2.0,
        label="冷媒温度",
    )
    axes.set_title("反応器内の温度分布")
    axes.set_xlabel("1本あたり触媒質量座標 [kg/tube]")
    axes.set_ylabel("温度 [K]")
    axes.grid(True, alpha=0.3)
    axes.legend()
    figure.tight_layout()
    figure.savefig(output_path)
    plt.close(figure)


def write_reaction_rate_profile_image(
    path: str | Path,
    profile: TemperatureProfile,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    figure, axes = plt.subplots(figsize=(9.6, 5.4), dpi=100)
    colors = ("#c43c30", "#2070b2", "#2f8f46")
    for color, (reaction_name, rates) in zip(
        colors,
        profile.reaction_rates_kmol_per_kgcat_h.items(),
    ):
        axes.plot(
            profile.catalyst_mass_kg,
            rates,
            linewidth=2.0,
            label=reaction_name,
            color=color,
        )
    axes.set_title("反応器内の反応速度分布")
    axes.set_xlabel("1本あたり触媒質量座標 [kg/tube]")
    axes.set_ylabel("反応速度 [kmol/(kgcat h)]")
    axes.set_yscale("symlog", linthresh=1.0e-8)
    axes.grid(True, which="both", alpha=0.3)
    axes.legend()
    figure.tight_layout()
    figure.savefig(output_path)
    plt.close(figure)


def write_temperature_profile_by_position_image(
    path: str | Path,
    profile: TemperatureProfile,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    figure, axes = plt.subplots(figsize=(9.6, 5.4), dpi=100)
    axes.plot(
        profile.reactor_coordinate_m,
        profile.gas_temperature_k,
        color="#c43c30",
        linewidth=2.0,
        label="管内ガス温度",
    )
    axes.plot(
        profile.reactor_coordinate_m,
        profile.coolant_temperature_k,
        color="#2070b2",
        linewidth=2.0,
        label="冷媒温度",
    )
    axes.set_title("反応器内の温度分布")
    axes.set_xlabel("反応器座標 z [m]")
    axes.set_ylabel("温度 [K]")
    axes.grid(True, alpha=0.3)
    axes.legend()
    figure.tight_layout()
    figure.savefig(output_path)
    plt.close(figure)


def write_reaction_rate_profile_by_position_image(
    path: str | Path,
    profile: TemperatureProfile,
) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    figure, axes = plt.subplots(figsize=(9.6, 5.4), dpi=100)
    colors = ("#c43c30", "#2070b2", "#2f8f46")
    for color, (reaction_name, rates) in zip(
        colors,
        profile.reaction_rates_kmol_per_kgcat_h.items(),
    ):
        axes.plot(
            profile.reactor_coordinate_m,
            rates,
            linewidth=2.0,
            label=reaction_name,
            color=color,
        )
    axes.set_title("反応器内の反応速度分布")
    axes.set_xlabel("反応器座標 z [m]")
    axes.set_ylabel("反応速度 [kmol/(kgcat h)]")
    axes.set_yscale("symlog", linthresh=1.0e-8)
    axes.grid(True, which="both", alpha=0.3)
    axes.legend()
    figure.tight_layout()
    figure.savefig(output_path)
    plt.close(figure)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Size a cooled packed-bed reactor network from JSON input."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Path to the reactor-design JSON input file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path to the JSON summary output file.",
    )
    parser.add_argument(
        "--profile-image",
        type=Path,
        default=DEFAULT_PROFILE_IMAGE_PATH,
        help="Path to the PNG temperature-profile output file.",
    )
    parser.add_argument(
        "--rate-profile-image",
        type=Path,
        default=DEFAULT_RATE_PROFILE_IMAGE_PATH,
        help="Path to the PNG reaction-rate-profile output file.",
    )
    parser.add_argument(
        "--position-profile-image",
        type=Path,
        default=DEFAULT_POSITION_PROFILE_IMAGE_PATH,
        help="Path to the z-axis PNG temperature-profile output file.",
    )
    parser.add_argument(
        "--position-rate-profile-image",
        type=Path,
        default=DEFAULT_POSITION_RATE_PROFILE_IMAGE_PATH,
        help="Path to the z-axis PNG reaction-rate-profile output file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    design_case = load_design_case(args.input)
    results = [
        evaluate_fixed_geometry(
            design_case=design_case,
            config=ReactorConfig(
                temperature_k=float(temperature_k),
                pressure_bar=design_case.pressure_bar,
                integration_steps=design_case.integration_steps,
            ),
        )
        for temperature_k in temperature_grid(design_case.temperature_sweep)
    ]
    write_summary(args.output, build_summary(design_case, results))
    hottest_result = max(results, key=lambda result: result.temperature_k)
    temperature_profile = temperature_profile_for_full_bed(
        design_case,
        hottest_result.temperature_k,
    )
    validate_profile_temperature_range(temperature_profile)
    write_temperature_profile_image(args.profile_image, temperature_profile)
    write_reaction_rate_profile_image(args.rate_profile_image, temperature_profile)
    write_temperature_profile_by_position_image(args.position_profile_image, temperature_profile)
    write_reaction_rate_profile_by_position_image(
        args.position_rate_profile_image,
        temperature_profile,
    )

    print("Reactions:")
    for reaction in design_case.reactions:
        print(f"  - {reaction.name}: {reaction.equation}")
    print(
        "Basis: non-isothermal multitube packed-bed reactor with countercurrent cooling, "
        f"P={design_case.pressure_bar:g} bar, "
        f"tubes={design_case.tube_count}, "
        f"total_feed={design_case.feed.flows_kmol_per_h}"
    )
    cooling = design_case.thermal.countercurrent_cooling
    print(
        "Cooling: "
        f"T_c,in={cooling.coolant_inlet_temperature_k:g} K, "
        f"total_flow={cooling.coolant_flow_kmol_per_h:g} kmol/h, "
        f"Cp={cooling.coolant_heat_capacity_kj_per_kmol_k:g} kJ/(kmol K), "
        f"UA={cooling.heat_transfer_ua_kj_per_kgcat_h_k:g} kJ/(kgcat h K)"
    )
    print(f"Summary JSON: {args.output}")
    print(f"Temperature profile PNG: {args.profile_image}")
    print(f"Reaction-rate profile PNG: {args.rate_profile_image}")
    print(f"Temperature profile by position PNG: {args.position_profile_image}")
    print(f"Reaction-rate profile by position PNG: {args.position_rate_profile_image}")
    print(format_sizing_table(results, design_case.metrics.target_species))


if __name__ == "__main__":
    main()

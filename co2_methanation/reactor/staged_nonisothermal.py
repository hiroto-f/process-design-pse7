"""Three-stage non-isothermal multitube reactor model using Xu kinetics."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any

from scipy.integrate import solve_ivp

from kinetics.xu_froment1989 import reaction_rates, species_rates


SPECIES = ("CO2", "H2", "CH4", "H2O", "CO")


@dataclass(frozen=True)
class ReactorConfig:
    pressure_bar: float
    tube_count: int
    tube_inner_diameter_m: float
    tube_length_per_stage_m: float
    catalyst_bulk_density_kg_per_m3: float
    fresh_catalyst: bool
    integration_steps_per_stage: int

    @property
    def catalyst_mass_per_tube_per_stage_kg(self) -> float:
        cross_section_m2 = math.pi * (self.tube_inner_diameter_m**2) / 4.0
        return (
            cross_section_m2
            * self.tube_length_per_stage_m
            * self.catalyst_bulk_density_kg_per_m3
        )

    @property
    def catalyst_mass_per_stage_kg(self) -> float:
        return self.catalyst_mass_per_tube_per_stage_kg * self.tube_count


@dataclass(frozen=True)
class StageConfig:
    count: int
    interstage_cooler_outlet_temperature_k: float
    tube_lengths_m: tuple[float, ...] | None = None
    interstage_cooler_outlet_temperatures_k: tuple[float, ...] | None = None


@dataclass(frozen=True)
class ThermalConfig:
    species_heat_capacity_kj_per_kmol_k: dict[str, float]
    reaction_enthalpy_kj_per_kmol: dict[str, float]


@dataclass(frozen=True)
class ExternalCoolingConfig:
    enabled: bool
    flow_pattern: str
    coolant_inlet_temperature_k: float
    coolant_heat_capacity_flow_kj_per_h_k: float
    overall_heat_transfer_coefficient_kj_per_m2_h_k: float
    coolant_inlet_temperatures_k: tuple[float, ...] | None = None


@dataclass(frozen=True)
class DesignCase:
    feed_flows_kmol_per_h: dict[str, float]
    feed_temperature_k: float
    reactor: ReactorConfig
    stages: StageConfig
    thermal: ThermalConfig
    external_cooling: ExternalCoolingConfig | None = None


@dataclass(frozen=True)
class StageResult:
    stage_index: int
    inlet_temperature_k: float
    reactor_outlet_temperature_k: float
    next_stage_inlet_temperature_k: float | None
    max_temperature_k: float
    inlet_flows_kmol_per_h: dict[str, float]
    outlet_flows_kmol_per_h: dict[str, float]
    co2_conversion: float
    h2_conversion: float
    intercooler_duty_kj_per_h: float
    coolant_inlet_temperature_k: float | None
    external_cooling_duty_kj_per_h: float
    coolant_outlet_temperature_k: float | None


@dataclass(frozen=True)
class ReactorResult:
    stages: tuple[StageResult, ...]
    outlet_flows_kmol_per_h: dict[str, float]
    overall_co2_conversion: float
    overall_h2_conversion: float
    ch4_generation_kmol_per_h: float
    ch4_yield_on_co2_feed: float
    ch4_selectivity_on_converted_co2: float
    total_catalyst_mass_kg: float
    total_intercooler_duty_kj_per_h: float
    total_external_cooling_duty_kj_per_h: float
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ReactorProfile:
    axial_position_m: tuple[float, ...]
    stage_index: tuple[int, ...]
    gas_temperature_k: tuple[float, ...]
    coolant_temperature_k: tuple[float, ...]
    reaction_rates_kmol_per_kgcat_h: dict[str, tuple[float, ...]]


def _as_float(value: Any, label: str) -> float:
    if not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    return float(value)


def _as_int(value: Any, label: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{label} must be an integer")
    return value


def load_design_case(path: str | Path) -> DesignCase:
    data = json.loads(Path(path).read_text())
    feed = data["feed"]
    reactor = data["reactor"]
    stages = data["stages"]
    thermal = data["thermal"]

    flows = {
        species: _as_float(feed["flows_kmol_per_h"][species], f"feed.{species}")
        for species in SPECIES
    }
    design_case = DesignCase(
        feed_flows_kmol_per_h=flows,
        feed_temperature_k=_as_float(feed["temperature_k"], "feed.temperature_k"),
        reactor=ReactorConfig(
            pressure_bar=_as_float(reactor["pressure_bar"], "reactor.pressure_bar"),
            tube_count=_as_int(reactor["tube_count"], "reactor.tube_count"),
            tube_inner_diameter_m=_as_float(
                reactor["tube_inner_diameter_m"],
                "reactor.tube_inner_diameter_m",
            ),
            tube_length_per_stage_m=_as_float(
                reactor["tube_length_per_stage_m"],
                "reactor.tube_length_per_stage_m",
            ),
            catalyst_bulk_density_kg_per_m3=_as_float(
                reactor["catalyst_bulk_density_kg_per_m3"],
                "reactor.catalyst_bulk_density_kg_per_m3",
            ),
            fresh_catalyst=bool(reactor["fresh_catalyst"]),
            integration_steps_per_stage=_as_int(
                reactor["integration_steps_per_stage"],
                "reactor.integration_steps_per_stage",
            ),
        ),
        stages=StageConfig(
            count=_as_int(stages["count"], "stages.count"),
            interstage_cooler_outlet_temperature_k=_as_float(
                stages["interstage_cooler_outlet_temperature_k"],
                "stages.interstage_cooler_outlet_temperature_k",
            ),
            tube_lengths_m=(
                tuple(
                    _as_float(value, f"stages.tube_lengths_m[{index}]")
                    for index, value in enumerate(stages["tube_lengths_m"])
                )
                if "tube_lengths_m" in stages
                else None
            ),
            interstage_cooler_outlet_temperatures_k=(
                tuple(
                    _as_float(
                        value,
                        f"stages.interstage_cooler_outlet_temperatures_k[{index}]",
                    )
                    for index, value in enumerate(
                        stages["interstage_cooler_outlet_temperatures_k"]
                    )
                )
                if "interstage_cooler_outlet_temperatures_k" in stages
                else None
            ),
        ),
        thermal=ThermalConfig(
            species_heat_capacity_kj_per_kmol_k={
                species: _as_float(
                    thermal["species_heat_capacity_kj_per_kmol_k"][species],
                    f"thermal.cp.{species}",
                )
                for species in SPECIES
            },
            reaction_enthalpy_kj_per_kmol={
                key: _as_float(value, f"thermal.dh.{key}")
                for key, value in thermal["reaction_enthalpy_kj_per_kmol"].items()
            },
        ),
        external_cooling=(
            ExternalCoolingConfig(
                enabled=bool(data["external_cooling"]["enabled"]),
                flow_pattern=str(data["external_cooling"]["flow_pattern"]),
                coolant_inlet_temperature_k=_as_float(
                    data["external_cooling"]["coolant_inlet_temperature_k"],
                    "external_cooling.coolant_inlet_temperature_k",
                ),
                coolant_inlet_temperatures_k=(
                    tuple(
                        _as_float(
                            value,
                            f"external_cooling.coolant_inlet_temperatures_k[{index}]",
                        )
                        for index, value in enumerate(
                            data["external_cooling"]["coolant_inlet_temperatures_k"]
                        )
                    )
                    if "coolant_inlet_temperatures_k" in data["external_cooling"]
                    else None
                ),
                coolant_heat_capacity_flow_kj_per_h_k=_as_float(
                    data["external_cooling"]["coolant_heat_capacity_flow_kj_per_h_k"],
                    "external_cooling.coolant_heat_capacity_flow_kj_per_h_k",
                ),
                overall_heat_transfer_coefficient_kj_per_m2_h_k=_as_float(
                    data["external_cooling"][
                        "overall_heat_transfer_coefficient_kj_per_m2_h_k"
                    ],
                    "external_cooling.overall_heat_transfer_coefficient_kj_per_m2_h_k",
                ),
            )
            if "external_cooling" in data
            else None
        ),
    )
    _validate_design_case(design_case)
    return design_case


def _validate_design_case(design_case: DesignCase) -> None:
    if design_case.reactor.pressure_bar <= 0.0:
        raise ValueError("pressure must be positive")
    if design_case.reactor.tube_count <= 0:
        raise ValueError("tube_count must be positive")
    if design_case.reactor.integration_steps_per_stage < 10:
        raise ValueError("integration_steps_per_stage must be at least 10")
    if design_case.stages.count <= 0:
        raise ValueError("stages.count must be positive")
    if (
        design_case.stages.tube_lengths_m is not None
        and len(design_case.stages.tube_lengths_m) != design_case.stages.count
    ):
        raise ValueError("stages.tube_lengths_m length must match stages.count")
    if (
        design_case.stages.interstage_cooler_outlet_temperatures_k is not None
        and len(design_case.stages.interstage_cooler_outlet_temperatures_k)
        != design_case.stages.count - 1
    ):
        raise ValueError(
            "stages.interstage_cooler_outlet_temperatures_k length must be stages.count - 1"
        )
    if set(design_case.thermal.reaction_enthalpy_kj_per_kmol) != {"R1", "R2", "R3"}:
        raise ValueError("reaction enthalpies must define R1, R2, and R3")
    if design_case.external_cooling is not None:
        cooling = design_case.external_cooling
        if cooling.flow_pattern != "co_current":
            raise ValueError("only co_current external cooling is currently supported")
        if (
            cooling.coolant_inlet_temperatures_k is not None
            and len(cooling.coolant_inlet_temperatures_k) != design_case.stages.count
        ):
            raise ValueError(
                "external_cooling.coolant_inlet_temperatures_k length must match stages.count"
            )
        if cooling.coolant_heat_capacity_flow_kj_per_h_k <= 0.0:
            raise ValueError("coolant heat capacity flow must be positive")
        if cooling.overall_heat_transfer_coefficient_kj_per_m2_h_k <= 0.0:
            raise ValueError("overall heat transfer coefficient must be positive")


def _partial_pressures(
    flows_kmol_per_h: dict[str, float],
    pressure_bar: float,
) -> dict[str, float]:
    total_flow = sum(max(flow, 0.0) for flow in flows_kmol_per_h.values())
    if total_flow <= 0.0:
        raise ValueError("total molar flow must stay positive")
    return {
        species: max(flows_kmol_per_h[species], 0.0) / total_flow * pressure_bar
        for species in SPECIES
    }


def _heat_capacity_flow_kj_per_h_k(
    flows_kmol_per_h: dict[str, float],
    thermal: ThermalConfig,
) -> float:
    value = sum(
        max(flows_kmol_per_h[species], 0.0)
        * thermal.species_heat_capacity_kj_per_kmol_k[species]
        for species in SPECIES
    )
    if value <= 0.0:
        raise ValueError("heat capacity flow must stay positive")
    return value


def _derivatives(
    flows_per_tube_kmol_per_h: dict[str, float],
    temperature_k: float,
    design_case: DesignCase,
) -> tuple[dict[str, float], float]:
    pressures = _partial_pressures(
        flows_per_tube_kmol_per_h,
        design_case.reactor.pressure_bar,
    )
    rates = reaction_rates(
        temperature_k,
        pressures,
        fresh_catalyst=design_case.reactor.fresh_catalyst,
    )
    flow_derivatives = species_rates(
        temperature_k,
        pressures,
        fresh_catalyst=design_case.reactor.fresh_catalyst,
    )
    heat_release_kj_per_kgcat_h = -(
        design_case.thermal.reaction_enthalpy_kj_per_kmol["R1"] * rates.reforming
        + design_case.thermal.reaction_enthalpy_kj_per_kmol["R2"]
        * rates.water_gas_shift
        + design_case.thermal.reaction_enthalpy_kj_per_kmol["R3"]
        * rates.overall_reforming
    )
    heat_capacity_flow = _heat_capacity_flow_kj_per_h_k(
        flows_per_tube_kmol_per_h,
        design_case.thermal,
    )
    return flow_derivatives, heat_release_kj_per_kgcat_h / heat_capacity_flow


def _external_heat_transfer_per_kgcat_h_k(
    design_case: DesignCase,
) -> float:
    reactor = design_case.reactor
    cooling = design_case.external_cooling
    if cooling is None or not cooling.enabled:
        return 0.0
    tube_surface_area_per_length_m2_per_m = math.pi * reactor.tube_inner_diameter_m
    catalyst_mass_per_length_kg_per_m = (
        math.pi * reactor.tube_inner_diameter_m**2 / 4.0
        * reactor.catalyst_bulk_density_kg_per_m3
    )
    return (
        cooling.overall_heat_transfer_coefficient_kj_per_m2_h_k
        * tube_surface_area_per_length_m2_per_m
        / catalyst_mass_per_length_kg_per_m
    )


def _rk4_step(
    flows_per_tube_kmol_per_h: dict[str, float],
    temperature_k: float,
    step_mass_kg: float,
    design_case: DesignCase,
) -> tuple[dict[str, float], float]:
    species = SPECIES

    def shifted(
        flows: dict[str, float],
        derivatives: dict[str, float],
        factor: float,
    ) -> dict[str, float]:
        return {
            key: max(flows[key] + factor * step_mass_kg * derivatives[key], 0.0)
            for key in species
        }

    k1_f, k1_t = _derivatives(flows_per_tube_kmol_per_h, temperature_k, design_case)
    k2_f, k2_t = _derivatives(
        shifted(flows_per_tube_kmol_per_h, k1_f, 0.5),
        temperature_k + 0.5 * step_mass_kg * k1_t,
        design_case,
    )
    k3_f, k3_t = _derivatives(
        shifted(flows_per_tube_kmol_per_h, k2_f, 0.5),
        temperature_k + 0.5 * step_mass_kg * k2_t,
        design_case,
    )
    k4_f, k4_t = _derivatives(
        shifted(flows_per_tube_kmol_per_h, k3_f, 1.0),
        temperature_k + step_mass_kg * k3_t,
        design_case,
    )
    next_flows = {
        key: max(
            flows_per_tube_kmol_per_h[key]
            + step_mass_kg
            * (k1_f[key] + 2.0 * k2_f[key] + 2.0 * k3_f[key] + k4_f[key])
            / 6.0,
            0.0,
        )
        for key in species
    }
    next_temperature = temperature_k + step_mass_kg * (
        k1_t + 2.0 * k2_t + 2.0 * k3_t + k4_t
    ) / 6.0
    return next_flows, next_temperature


def simulate_with_profile(design_case: DesignCase) -> tuple[ReactorResult, ReactorProfile]:
    reactor = design_case.reactor
    per_tube_flows = {
        species: flow / reactor.tube_count
        for species, flow in design_case.feed_flows_kmol_per_h.items()
    }
    gas_temperature_k = design_case.feed_temperature_k
    stage_results: list[StageResult] = []
    total_intercooler_duty = 0.0
    total_external_cooling_duty = 0.0
    warnings: list[str] = []
    axial_position_m: list[float] = []
    profile_stage_index: list[int] = []
    gas_temperature_profile_k: list[float] = []
    coolant_temperature_profile_k: list[float] = []
    reaction_rate_profiles = {"R1": [], "R2": [], "R3": []}
    stage_lengths_m = (
        design_case.stages.tube_lengths_m
        if design_case.stages.tube_lengths_m is not None
        else tuple(
            reactor.tube_length_per_stage_m for _ in range(design_case.stages.count)
        )
    )
    stage_position_offset = 0.0
    catalyst_mass_total_kg = 0.0

    for stage_index in range(1, design_case.stages.count + 1):
        stage_length_m = stage_lengths_m[stage_index - 1]
        stage_mass_per_tube = (
            math.pi * reactor.tube_inner_diameter_m**2 / 4.0
            * stage_length_m
            * reactor.catalyst_bulk_density_kg_per_m3
        )
        catalyst_mass_total_kg += stage_mass_per_tube * reactor.tube_count
        step_mass = stage_mass_per_tube / reactor.integration_steps_per_stage
        inlet_flows_total = {
            species: flow * reactor.tube_count for species, flow in per_tube_flows.items()
        }
        inlet_temperature = gas_temperature_k
        max_temperature = gas_temperature_k
        initial_state = [per_tube_flows[species] for species in SPECIES] + [
            gas_temperature_k
        ]
        stage_coolant_temperature_k = (
            design_case.external_cooling.coolant_inlet_temperatures_k[stage_index - 1]
            if design_case.external_cooling is not None
            and design_case.external_cooling.enabled
            and design_case.external_cooling.coolant_inlet_temperatures_k is not None
            else (
                design_case.external_cooling.coolant_inlet_temperature_k
                if design_case.external_cooling is not None
                and design_case.external_cooling.enabled
                else gas_temperature_k
            )
        )
        if design_case.external_cooling is not None and design_case.external_cooling.enabled:
            initial_state.append(stage_coolant_temperature_k)

        def ode(_: float, state: list[float]) -> list[float]:
            stage_flows = {
                species: max(state[index], 1e-20)
                for index, species in enumerate(SPECIES)
            }
            flow_derivatives, temperature_derivative = _derivatives(
                stage_flows,
                state[-1],
                design_case,
            )
            values = [flow_derivatives[species] for species in SPECIES]
            if design_case.external_cooling is None or not design_case.external_cooling.enabled:
                return values + [temperature_derivative]
            heat_transfer_per_kgcat_h_k = _external_heat_transfer_per_kgcat_h_k(
                design_case
            )
            coolant_temperature_k = state[-1]
            heat_capacity_flow = _heat_capacity_flow_kj_per_h_k(
                stage_flows,
                design_case.thermal,
            )
            heat_removed_per_kgcat_h = heat_transfer_per_kgcat_h_k * (
                state[-2] - coolant_temperature_k
            )
            coolant_cp_per_tube = (
                design_case.external_cooling.coolant_heat_capacity_flow_kj_per_h_k
                / design_case.reactor.tube_count
            )
            return values + [
                temperature_derivative - heat_removed_per_kgcat_h / heat_capacity_flow,
                heat_removed_per_kgcat_h / coolant_cp_per_tube,
            ]

        if stage_mass_per_tube <= 1.0e-8:
            state_columns = [initial_state]
        else:
            evaluation_points = [
                stage_mass_per_tube * step_index / reactor.integration_steps_per_stage
                for step_index in range(reactor.integration_steps_per_stage + 1)
            ]
            evaluation_points[-1] = stage_mass_per_tube
            solution = solve_ivp(
                ode,
                (0.0, stage_mass_per_tube),
                initial_state,
                method="BDF",
                t_eval=evaluation_points,
                atol=1e-10,
                rtol=1e-8,
            )
            if not solution.success:
                raise RuntimeError(
                    f"stage {stage_index} integration failed: {solution.message}"
                )
            state_columns = [
                [
                    float(solution.y[row_index, column_index])
                    for row_index in range(solution.y.shape[0])
                ]
                for column_index in range(solution.y.shape[1])
            ]

        sample_count = len(state_columns)
        for step_index, state in enumerate(state_columns):
            per_tube_flows = {
                species: max(float(state[index]), 0.0)
                for index, species in enumerate(SPECIES)
            }
            gas_temperature_k = float(
                state[-2]
                if design_case.external_cooling is not None
                and design_case.external_cooling.enabled
                else state[-1]
            )
            stage_coolant_temperature_k = float(state[-1])
            axial_position_m.append(
                stage_position_offset
                + stage_length_m
                * step_index
                / max(sample_count - 1, 1)
            )
            profile_stage_index.append(stage_index)
            gas_temperature_profile_k.append(gas_temperature_k)
            coolant_temperature_profile_k.append(stage_coolant_temperature_k)
            rates = reaction_rates(
                gas_temperature_k,
                _partial_pressures(per_tube_flows, reactor.pressure_bar),
                fresh_catalyst=reactor.fresh_catalyst,
            )
            reaction_rate_profiles["R1"].append(rates.reforming)
            reaction_rate_profiles["R2"].append(rates.water_gas_shift)
            reaction_rate_profiles["R3"].append(rates.overall_reforming)
            max_temperature = max(max_temperature, gas_temperature_k)

        reactor_outlet_temperature = gas_temperature_k
        external_cooling_duty = 0.0
        coolant_inlet_temperature_k = None
        coolant_outlet_temperature_k = None
        if design_case.external_cooling is not None and design_case.external_cooling.enabled:
            coolant_inlet_temperature_k = (
                design_case.external_cooling.coolant_inlet_temperatures_k[stage_index - 1]
                if design_case.external_cooling.coolant_inlet_temperatures_k is not None
                else design_case.external_cooling.coolant_inlet_temperature_k
            )
            coolant_outlet_temperature_k = stage_coolant_temperature_k
            external_cooling_duty = (
                design_case.external_cooling.coolant_heat_capacity_flow_kj_per_h_k
                * (
                    coolant_outlet_temperature_k
                    - coolant_inlet_temperature_k
                )
            )
            total_external_cooling_duty += external_cooling_duty
        outlet_flows_total = {
            species: flow * reactor.tube_count for species, flow in per_tube_flows.items()
        }
        stage_co2_conversion = (
            inlet_flows_total["CO2"] - outlet_flows_total["CO2"]
        ) / max(inlet_flows_total["CO2"], 1e-20)
        stage_h2_conversion = (
            inlet_flows_total["H2"] - outlet_flows_total["H2"]
        ) / max(inlet_flows_total["H2"], 1e-20)

        intercooler_duty = 0.0
        if stage_index < design_case.stages.count:
            target_temperature = (
                design_case.stages.interstage_cooler_outlet_temperatures_k[
                    stage_index - 1
                ]
                if design_case.stages.interstage_cooler_outlet_temperatures_k
                is not None
                else design_case.stages.interstage_cooler_outlet_temperature_k
            )
            heat_capacity_flow = _heat_capacity_flow_kj_per_h_k(
                outlet_flows_total,
                design_case.thermal,
            )
            intercooler_duty = max(
                heat_capacity_flow * (gas_temperature_k - target_temperature),
                0.0,
            )
            total_intercooler_duty += intercooler_duty
            gas_temperature_k = target_temperature

        if max_temperature > 873.15:
            warnings.append(
                f"stage {stage_index} exceeds accepted methanation range: "
                f"max temperature {max_temperature:.2f} K > 873.15 K"
            )

        stage_results.append(
            StageResult(
                stage_index=stage_index,
                inlet_temperature_k=inlet_temperature,
                reactor_outlet_temperature_k=reactor_outlet_temperature,
                next_stage_inlet_temperature_k=(
                    gas_temperature_k if stage_index < design_case.stages.count else None
                ),
                max_temperature_k=max_temperature,
                inlet_flows_kmol_per_h=inlet_flows_total,
                outlet_flows_kmol_per_h=outlet_flows_total,
                co2_conversion=stage_co2_conversion,
                h2_conversion=stage_h2_conversion,
                intercooler_duty_kj_per_h=intercooler_duty,
                coolant_inlet_temperature_k=coolant_inlet_temperature_k,
                external_cooling_duty_kj_per_h=external_cooling_duty,
                coolant_outlet_temperature_k=coolant_outlet_temperature_k,
            )
        )
        stage_position_offset += stage_length_m

    outlet_flows_total = stage_results[-1].outlet_flows_kmol_per_h
    feed = design_case.feed_flows_kmol_per_h
    result = ReactorResult(
        stages=tuple(stage_results),
        outlet_flows_kmol_per_h=outlet_flows_total,
        overall_co2_conversion=(feed["CO2"] - outlet_flows_total["CO2"]) / feed["CO2"],
        overall_h2_conversion=(feed["H2"] - outlet_flows_total["H2"]) / feed["H2"],
        ch4_generation_kmol_per_h=outlet_flows_total["CH4"] - feed["CH4"],
        ch4_yield_on_co2_feed=(outlet_flows_total["CH4"] - feed["CH4"])
        / feed["CO2"],
        ch4_selectivity_on_converted_co2=(
            (outlet_flows_total["CH4"] - feed["CH4"])
            / max(feed["CO2"] - outlet_flows_total["CO2"], 1e-20)
        ),
        total_catalyst_mass_kg=catalyst_mass_total_kg,
        total_intercooler_duty_kj_per_h=total_intercooler_duty,
        total_external_cooling_duty_kj_per_h=total_external_cooling_duty,
        warnings=tuple(warnings),
    )
    profile = ReactorProfile(
        axial_position_m=tuple(axial_position_m),
        stage_index=tuple(profile_stage_index),
        gas_temperature_k=tuple(gas_temperature_profile_k),
        coolant_temperature_k=tuple(coolant_temperature_profile_k),
        reaction_rates_kmol_per_kgcat_h={
            key: tuple(values) for key, values in reaction_rate_profiles.items()
        },
    )
    return result, profile


def simulate(design_case: DesignCase) -> ReactorResult:
    result, _ = simulate_with_profile(design_case)
    return result


def result_to_dict(result: ReactorResult) -> dict[str, Any]:
    return {
        "stages": [
            {
                "stage_index": stage.stage_index,
                "inlet_temperature_k": stage.inlet_temperature_k,
                "reactor_outlet_temperature_k": stage.reactor_outlet_temperature_k,
                "next_stage_inlet_temperature_k": stage.next_stage_inlet_temperature_k,
                "max_temperature_k": stage.max_temperature_k,
                "co2_conversion": stage.co2_conversion,
                "h2_conversion": stage.h2_conversion,
                "intercooler_duty_kj_per_h": stage.intercooler_duty_kj_per_h,
                "coolant_inlet_temperature_k": stage.coolant_inlet_temperature_k,
                "external_cooling_duty_kj_per_h": stage.external_cooling_duty_kj_per_h,
                "coolant_outlet_temperature_k": stage.coolant_outlet_temperature_k,
                "inlet_flows_kmol_per_h": stage.inlet_flows_kmol_per_h,
                "outlet_flows_kmol_per_h": stage.outlet_flows_kmol_per_h,
            }
            for stage in result.stages
        ],
        "outlet_flows_kmol_per_h": result.outlet_flows_kmol_per_h,
        "overall_co2_conversion": result.overall_co2_conversion,
        "overall_h2_conversion": result.overall_h2_conversion,
        "ch4_generation_kmol_per_h": result.ch4_generation_kmol_per_h,
        "ch4_yield_on_co2_feed": result.ch4_yield_on_co2_feed,
        "ch4_selectivity_on_converted_co2": result.ch4_selectivity_on_converted_co2,
        "total_catalyst_mass_kg": result.total_catalyst_mass_kg,
        "total_intercooler_duty_kj_per_h": result.total_intercooler_duty_kj_per_h,
        "total_external_cooling_duty_kj_per_h": result.total_external_cooling_duty_kj_per_h,
        "warnings": list(result.warnings),
    }

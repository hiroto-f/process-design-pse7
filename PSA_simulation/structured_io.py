from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .models import (
    AdsorbentInput,
    ComponentInput,
    FeedComponentInput,
    FeedInput,
    SimulationInput,
    TowerInput,
)
from .preprocess import SetupState
from .simulator import SimulationState


PROFILE_FILES = {
    "adsorption_1": "adsorption_1_profile.csv",
    "desorption": "desorption_profile.csv",
    "adsorption_2": "adsorption_2_profile.csv",
}


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_common_inputs(common_dir: Path) -> tuple[AdsorbentInput, tuple[ComponentInput, ComponentInput]]:
    adsorbent_data = load_json(common_dir / "adsorbent.json")
    component_data = load_json(common_dir / "components.json")
    adsorbent = AdsorbentInput(**adsorbent_data)
    components = tuple(
        ComponentInput(name=name, **component_data[name])
        for name in ("H2", "CH4")
    )
    return adsorbent, components


def load_tower_input(
    tower_path: Path,
    adsorbent: AdsorbentInput,
    components: tuple[ComponentInput, ComponentInput],
) -> SimulationInput:
    raw = load_json(tower_path)
    tower = TowerInput(**raw["tower"])
    ordered_feed = _ordered_feed_components(raw["feed"]["components_kmol_per_h"])
    feed = FeedInput(
        temperature_k=raw["feed"].get("temperature_k"),
        pressure_kpa=raw["feed"].get("pressure_kpa"),
        volume_flow_m3_per_h=raw["feed"].get("volume_flow_m3_per_h"),
        components_kmol_per_h=tuple(
            FeedComponentInput(**component) for component in ordered_feed
        ),
    )
    return SimulationInput(
        adsorbent=adsorbent,
        components=components,
        tower=tower,
        feed=feed,
    )


def save_outputs(
    inputs: SimulationInput,
    output_dir: Path,
    tower_name: str,
    setup_state: SetupState,
    simulation_state: SimulationState | None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    summary = _build_summary(inputs, tower_name, setup_state, simulation_state)
    with (output_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    if simulation_state is None:
        return

    for profile_name, filename in PROFILE_FILES.items():
        _save_profile_csv(output_dir / filename, simulation_state.profiles[profile_name])


def _ordered_feed_components(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_name = {component["name"]: component for component in components}
    missing = [name for name in ("H2", "CH4") if name not in by_name]
    if missing:
        missing_text = ", ".join(missing)
        raise ValueError(f"feed.components_kmol_per_h is missing required components: {missing_text}")

    ordered = [by_name["H2"], by_name["CH4"]]
    ordered.extend(component for component in components if component["name"] not in {"H2", "CH4"})
    return ordered


def _save_profile_csv(path: Path, snapshots) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_s", "position_m", "C_H2", "C_CH4", "q_H2", "q_CH4", "u"])
        for snapshot in snapshots:
            for position_m, c_h2, c_ch4, q_h2, q_ch4, u in snapshot.rows:
                writer.writerow([snapshot.time_s, position_m, c_h2, c_ch4, q_h2, q_ch4, u])


def _build_summary(
    inputs: SimulationInput,
    tower_name: str,
    setup_state: SetupState,
    simulation_state: SimulationState | None,
) -> dict[str, Any]:
    components = []
    for name, flow, mole_fraction, two_fraction in zip(
        setup_state.component_names,
        setup_state.flows_kmol_per_h,
        setup_state.mol_fractions,
        setup_state.two_fractions,
    ):
        components.append(
            {
                "name": name,
                "flow_kmol_per_h": flow,
                "mole_fraction": mole_fraction,
                "two_component_fraction": two_fraction,
            }
        )

    summary: dict[str, Any] = {
        "tower_name": tower_name,
        "feed": {
            "temperature_k": setup_state.tt,
            "pressure_kpa": setup_state.feed_pressure_kpa,
            "volume_flow_m3_per_h": setup_state.volume_flow_m3_per_h,
            "average_molar_mass_g_per_mol": setup_state.mav,
            "components": components,
        },
        "setup": {
            "adsorption_pressure_kpa": setup_state.phigh,
            "desorption_pressure_kpa": setup_state.plow,
            "tower_temperature_k": setup_state.tt,
            "tower_height_m": setup_state.zt,
            "tower_diameter_m": setup_state.dto,
            "adsorption_velocity_m_per_s": setup_state.uhigh,
            "desorption_velocity_m_per_s": setup_state.ulow,
            "reflux_factor": setup_state.reflux,
            "molar_flow_mol_per_s": setup_state.qt,
        },
    }

    if simulation_state is None:
        return summary

    hydrogen_feed = setup_state.flows_kmol_per_h[0]
    hydrogen_product = simulation_state.product_out[0]
    summary["performance"] = {
        "adsorption_end_time_s": simulation_state.end_time[0],
        "desorption_end_time_s": simulation_state.end_time[1],
        "product_kmol": {
            "H2": simulation_state.product_out[0],
            "CH4": simulation_state.product_out[1],
        },
        "regeneration_inlet_concentration_kmol_per_m3": {
            "H2": simulation_state.regeneration_inlet_concentration[0],
            "CH4": simulation_state.regeneration_inlet_concentration[1],
        },
        "offgas_kmol": {
            "H2": simulation_state.purge_out[0],
            "CH4": simulation_state.purge_out[1],
        },
        "hydrogen_recovery_percent": hydrogen_product / hydrogen_feed * 100.0 if hydrogen_feed else None,
    }
    return summary

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
from .simulators import SimulationState


PROFILE_FILES = {
    "adsorption_1": "adsorption_1_profile.csv",
    "desorption": "desorption_profile.csv",
    "adsorption_2": "adsorption_2_profile.csv",
}
DESORPTION_OUTLET_FILE = "desorption_outlet_ch4_curve.csv"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
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
    if simulation_state.desorption_outlet_history:
        _save_desorption_outlet_csv(output_dir / DESORPTION_OUTLET_FILE, simulation_state.desorption_outlet_history)


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


def _save_desorption_outlet_csv(path: Path, outlet_history) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "time_s",
                "C_H2_out_kmol_per_m3",
                "C_CH4_out_kmol_per_m3",
                "y_CH4_out",
                "u_out_m_per_s",
                "is_product_cut",
            ]
        )
        writer.writerows(outlet_history)


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
            "purge_fraction": setup_state.purge_fraction,
            "desorption_velocity_m_per_s": setup_state.ulow,
            "adsorption_breakthrough_threshold": setup_state.adsorption_breakthrough_threshold,
            "desorption_residual_loading_threshold": setup_state.desorption_residual_loading_threshold,
            "reflux_factor": setup_state.reflux,
            "molar_flow_mol_per_s": setup_state.qt,
        },
    }

    if simulation_state is None:
        return summary

    hydrogen_feed_rate = setup_state.flows_kmol_per_h[0]
    methane_feed_rate = setup_state.flows_kmol_per_h[1]
    adsorption_time_h = simulation_state.end_time[0] / 3600.0
    hydrogen_feed_kmol = hydrogen_feed_rate * adsorption_time_h
    methane_feed_kmol = methane_feed_rate * adsorption_time_h
    feed_h2_ch4_kmol = hydrogen_feed_kmol + methane_feed_kmol
    feed_methane_mole_fraction = methane_feed_kmol / feed_h2_ch4_kmol if feed_h2_ch4_kmol else None
    cycle_time_s = simulation_state.end_time[0] + simulation_state.end_time[1]
    hydrogen_product_kmol = simulation_state.purge_out[0]
    methane_product_kmol = simulation_state.purge_out[1]
    desorption_product_kmol = hydrogen_product_kmol + methane_product_kmol
    methane_product_mole_fraction = (
        methane_product_kmol / desorption_product_kmol if desorption_product_kmol else None
    )
    cut_hydrogen_product_kmol = simulation_state.product_cut_out[0]
    cut_methane_product_kmol = simulation_state.product_cut_out[1]
    cut_product_kmol = cut_hydrogen_product_kmol + cut_methane_product_kmol
    cut_methane_product_mole_fraction = (
        cut_methane_product_kmol / cut_product_kmol if cut_product_kmol else None
    )
    summary["performance"] = {
        "adsorption_end_time_s": simulation_state.end_time[0],
        "desorption_end_time_s": simulation_state.end_time[1],
        "cycle_time_s": cycle_time_s,
        "adsorption_feed_kmol": {
            "H2": hydrogen_feed_kmol,
            "CH4": methane_feed_kmol,
        },
        "recycle_kmol": {
            "H2": simulation_state.product_out[0],
            "CH4": simulation_state.product_out[1],
        },
        "desorption_product_kmol": {
            "H2": hydrogen_product_kmol,
            "CH4": methane_product_kmol,
        },
        "product_cut": {
            "ch4_min_mole_fraction": simulation_state.product_cut_ch4_min_fraction,
            "start_time_s": simulation_state.product_cut_start_time_s,
            "end_time_s": simulation_state.product_cut_end_time_s,
            "duration_s": simulation_state.product_cut_duration_s,
            "product_kmol": {
                "H2": cut_hydrogen_product_kmol,
                "CH4": cut_methane_product_kmol,
            },
            "methane_mole_fraction": cut_methane_product_mole_fraction,
            "methane_recovery_percent": (
                cut_methane_product_kmol / methane_feed_kmol * 100.0 if methane_feed_kmol else None
            ),
        },
        "regeneration_inlet_concentration_kmol_per_m3": {
            "H2": simulation_state.regeneration_inlet_concentration[0],
            "CH4": simulation_state.regeneration_inlet_concentration[1],
        },
        "feed_methane_mole_fraction_h2_ch4": feed_methane_mole_fraction,
        "desorption_product_methane_mole_fraction": methane_product_mole_fraction,
        "methane_enrichment_factor": (
            methane_product_mole_fraction / feed_methane_mole_fraction
            if methane_product_mole_fraction is not None and feed_methane_mole_fraction
            else None
        ),
        "hydrogen_contamination_in_desorption_product_kmol": hydrogen_product_kmol,
        "methane_desorption_recovery_percent": (
            methane_product_kmol / methane_feed_kmol * 100.0 if methane_feed_kmol else None
        ),
    }
    return summary

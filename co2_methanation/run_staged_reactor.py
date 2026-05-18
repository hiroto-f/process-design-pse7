"""Run the three-stage non-isothermal Xu reactor case."""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import replace

import matplotlib.pyplot as plt

from reactor.staged_nonisothermal import (
    ReactorProfile,
    load_design_case,
    result_to_dict,
    simulate_with_profile,
)


PACKAGE_DIR = Path(__file__).parent
INPUT_PATH = PACKAGE_DIR / "inputs" / "staged_reactor.json"
OUTPUT_ROOT = PACKAGE_DIR / "outputs" / "adiabatic_sweep"
OUTPUT_PATH = OUTPUT_ROOT / "summary.json"
FEASIBLE_OUTPUT_PATH = OUTPUT_ROOT / "feasible_cases.json"
TEMPERATURE_SWEEP_K = tuple(573.15 + 10.0 * index for index in range(11))
MIN_GAS_TEMPERATURE_K = 573.15
MAX_GAS_TEMPERATURE_K = 673.15


def _plot_temperature_profile(profile: ReactorProfile, output_path: Path) -> None:
    plt.figure(figsize=(8, 5))
    plt.plot(profile.axial_position_m, profile.gas_temperature_k, linewidth=2)
    boundaries = [
        profile.axial_position_m[index]
        for index in range(1, len(profile.stage_index))
        if profile.stage_index[index] != profile.stage_index[index - 1]
    ]
    for boundary_m in boundaries:
        plt.axvline(boundary_m, color="0.6", linestyle="--", linewidth=1)
    plt.xlabel("Axial position z [m]")
    plt.ylabel("Gas temperature [K]")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def _plot_reaction_rate_profile(profile: ReactorProfile, output_path: Path) -> None:
    plt.figure(figsize=(8, 5))
    labels = {
        "R1": "R1: reforming",
        "R2": "R2: water-gas shift",
        "R3": "R3: overall reforming",
    }
    for reaction_name, values in profile.reaction_rates_kmol_per_kgcat_h.items():
        plt.plot(
            profile.axial_position_m,
            values,
            linewidth=2,
            label=labels[reaction_name],
        )
    boundaries = [
        profile.axial_position_m[index]
        for index in range(1, len(profile.stage_index))
        if profile.stage_index[index] != profile.stage_index[index - 1]
    ]
    for boundary_m in boundaries:
        plt.axvline(boundary_m, color="0.6", linestyle="--", linewidth=1)
    plt.xlabel("Axial position z [m]")
    plt.ylabel("Reaction rate [kmol/(kgcat h)]")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def main() -> None:
    base_case = load_design_case(INPUT_PATH)
    sweep_results: dict[str, dict[str, object]] = {}
    feasible_results: dict[str, dict[str, object]] = {}

    for inlet_temperature_k in TEMPERATURE_SWEEP_K:
        for interstage_temperature_k in TEMPERATURE_SWEEP_K:
            case = replace(
                base_case,
                feed_temperature_k=inlet_temperature_k,
                stages=replace(
                    base_case.stages,
                    interstage_cooler_outlet_temperature_k=interstage_temperature_k,
                ),
            )
            result, profile = simulate_with_profile(case)
            minimum_temperature_k = min(profile.gas_temperature_k)
            maximum_temperature_k = max(profile.gas_temperature_k)
            feasible = (
                minimum_temperature_k >= MIN_GAS_TEMPERATURE_K
                and maximum_temperature_k <= MAX_GAS_TEMPERATURE_K
            )
            case_name = (
                f"inlet_{inlet_temperature_k:.2f}K_"
                f"interstage_{interstage_temperature_k:.2f}K"
            )
            case_output_dir = OUTPUT_ROOT / case_name
            case_output_dir.mkdir(parents=True, exist_ok=True)
            case_summary = {
                "inlet_temperature_k": inlet_temperature_k,
                "interstage_cooler_outlet_temperature_k": interstage_temperature_k,
                "minimum_gas_temperature_k": minimum_temperature_k,
                "maximum_gas_temperature_k": maximum_temperature_k,
                "within_target_temperature_window": feasible,
                **result_to_dict(result),
            }
            (case_output_dir / "summary.json").write_text(json.dumps(case_summary, indent=2))
            _plot_temperature_profile(profile, case_output_dir / "temperature_profile.png")
            _plot_reaction_rate_profile(profile, case_output_dir / "reaction_rate_profile.png")
            sweep_results[case_name] = case_summary
            if feasible:
                feasible_results[case_name] = case_summary

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(sweep_results, indent=2))
    FEASIBLE_OUTPUT_PATH.write_text(json.dumps(feasible_results, indent=2))
    print(json.dumps(feasible_results, indent=2))


if __name__ == "__main__":
    main()

"""Fine sweep of coolant temperature for the four-stage co-current reactor."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import matplotlib.pyplot as plt

from run_coolant_temperature_sweep_cocurrent import (
    MAX_TUBE_LENGTH_M,
    _find_minimum_tube_count_for_length_limit,
)
from run_staged_reactor import _plot_reaction_rate_profile, _plot_temperature_profile
from reactor.staged_nonisothermal import load_design_case, result_to_dict, simulate_with_profile


PACKAGE_DIR = Path(__file__).parent
INPUT_PATH = PACKAGE_DIR / "inputs" / "four_stage_300c_to_400c_cocurrent.json"
OUTPUT_DIR = PACKAGE_DIR / "outputs" / "coolant_temperature_fine_sweep_cocurrent"
COOLANT_TEMPERATURES_K = tuple(543.15 + float(index) for index in range(11))
MIN_ALLOWED_GAS_TEMPERATURE_K = 573.15


def _plot_metric(results, key: str, ylabel: str, output_path: Path, multiplier: float = 1.0):
    plt.figure(figsize=(8, 5))
    plt.plot(
        [result["coolant_inlet_temperature_k"] for result in results],
        [multiplier * result[key] for result in results],
        marker="o",
        linewidth=2,
    )
    plt.xlabel("Coolant inlet temperature [K]")
    plt.ylabel(ylabel)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def main() -> None:
    base_case = load_design_case(INPUT_PATH)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []

    for coolant_temperature_k in COOLANT_TEMPERATURES_K:
        cooled_case = replace(
            base_case,
            external_cooling=replace(
                base_case.external_cooling,
                coolant_inlet_temperature_k=coolant_temperature_k,
            ),
        )
        tube_count, lengths_m = _find_minimum_tube_count_for_length_limit(cooled_case)
        design_case = replace(
            cooled_case,
            reactor=replace(cooled_case.reactor, tube_count=tube_count),
            stages=replace(cooled_case.stages, tube_lengths_m=lengths_m),
        )
        result, profile = simulate_with_profile(design_case)
        case_output_dir = OUTPUT_DIR / f"{coolant_temperature_k:.2f}K"
        case_output_dir.mkdir(parents=True, exist_ok=True)
        minimum_gas_temperature_k = min(profile.gas_temperature_k)
        summary = {
            "coolant_inlet_temperature_k": coolant_temperature_k,
            "tube_count": tube_count,
            "maximum_tube_length_limit_m": MAX_TUBE_LENGTH_M,
            "sized_stage_lengths_m": list(lengths_m),
            "minimum_gas_temperature_k": minimum_gas_temperature_k,
            "maximum_gas_temperature_k": max(profile.gas_temperature_k),
            "within_minimum_temperature_limit": (
                minimum_gas_temperature_k >= MIN_ALLOWED_GAS_TEMPERATURE_K
            ),
            **result_to_dict(result),
        }
        (case_output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
        _plot_temperature_profile(profile, case_output_dir / "temperature_profile.png")
        _plot_reaction_rate_profile(profile, case_output_dir / "reaction_rate_profile.png")
        results.append(summary)

    (OUTPUT_DIR / "summary.json").write_text(json.dumps(results, indent=2))
    feasible_results = [
        result for result in results if result["within_minimum_temperature_limit"]
    ]
    (OUTPUT_DIR / "feasible_cases.json").write_text(
        json.dumps(feasible_results, indent=2)
    )
    _plot_metric(
        results,
        "overall_co2_conversion",
        "Overall CO2 conversion [%]",
        OUTPUT_DIR / "co2_conversion_vs_coolant_temperature.png",
        multiplier=100.0,
    )
    _plot_metric(
        results,
        "minimum_gas_temperature_k",
        "Minimum gas temperature [K]",
        OUTPUT_DIR / "minimum_gas_temperature_vs_coolant_temperature.png",
    )
    _plot_metric(
        results,
        "tube_count",
        "Minimum tube count [-]",
        OUTPUT_DIR / "tube_count_vs_coolant_temperature.png",
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

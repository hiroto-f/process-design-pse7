"""Sweep tube count while resizing each stage to end at 400 C."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import matplotlib.pyplot as plt

from run_four_stage_300c_to_400c_cocurrent import _size_lengths
from run_staged_reactor import _plot_reaction_rate_profile, _plot_temperature_profile
from reactor.staged_nonisothermal import load_design_case, result_to_dict, simulate_with_profile


PACKAGE_DIR = Path(__file__).parent
INPUT_PATH = PACKAGE_DIR / "inputs" / "four_stage_300c_to_400c_cocurrent.json"
OUTPUT_DIR = PACKAGE_DIR / "outputs" / "tube_count_sweep_target_temperature_cocurrent"
TUBE_COUNTS = (100, 200, 300, 500, 750, 1000)


def _plot_metric(
    results: list[dict[str, object]],
    key: str,
    ylabel: str,
    output_path: Path,
    multiplier: float = 1.0,
) -> None:
    plt.figure(figsize=(8, 5))
    plt.plot(
        [result["tube_count"] for result in results],
        [multiplier * result[key] for result in results],
        marker="o",
        linewidth=2,
    )
    plt.xlabel("Tube count [-]")
    plt.ylabel(ylabel)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def main() -> None:
    base_case = load_design_case(INPUT_PATH)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []

    for tube_count in TUBE_COUNTS:
        count_case = replace(
            base_case,
            reactor=replace(base_case.reactor, tube_count=tube_count),
        )
        lengths_m = _size_lengths(count_case)
        design_case = replace(
            count_case,
            stages=replace(count_case.stages, tube_lengths_m=lengths_m),
        )
        result, profile = simulate_with_profile(design_case)
        case_output_dir = OUTPUT_DIR / f"{tube_count}_tubes"
        case_output_dir.mkdir(parents=True, exist_ok=True)
        summary = {
            "tube_count": tube_count,
            "sized_stage_lengths_m": list(lengths_m),
            "minimum_gas_temperature_k": min(profile.gas_temperature_k),
            "maximum_gas_temperature_k": max(profile.gas_temperature_k),
            **result_to_dict(result),
        }
        (case_output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
        _plot_temperature_profile(profile, case_output_dir / "temperature_profile.png")
        _plot_reaction_rate_profile(profile, case_output_dir / "reaction_rate_profile.png")
        results.append(summary)

    (OUTPUT_DIR / "summary.json").write_text(json.dumps(results, indent=2))
    _plot_metric(
        results,
        "overall_co2_conversion",
        "Overall CO2 conversion [%]",
        OUTPUT_DIR / "co2_conversion_vs_tube_count.png",
        multiplier=100.0,
    )
    _plot_metric(
        results,
        "total_catalyst_mass_kg",
        "Total catalyst mass [kg]",
        OUTPUT_DIR / "catalyst_mass_vs_tube_count.png",
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

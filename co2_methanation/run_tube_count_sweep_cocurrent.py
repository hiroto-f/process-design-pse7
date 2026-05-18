"""Sweep tube count for the four-stage co-current wall-cooled reactor."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import matplotlib.pyplot as plt

from run_staged_reactor import _plot_reaction_rate_profile, _plot_temperature_profile
from reactor.staged_nonisothermal import load_design_case, result_to_dict, simulate_with_profile


PACKAGE_DIR = Path(__file__).parent
INPUT_PATH = PACKAGE_DIR / "inputs" / "four_stage_300c_to_400c_cocurrent.json"
BASELINE_SUMMARY_PATH = (
    PACKAGE_DIR
    / "outputs"
    / "four_stage_300c_to_400c_cocurrent"
    / "summary.json"
)
OUTPUT_DIR = PACKAGE_DIR / "outputs" / "tube_count_sweep_cocurrent"
TUBE_COUNTS = (100, 200, 300, 500, 750, 1000)


def _plot_conversion_sweep(results: list[dict[str, object]], output_path: Path) -> None:
    plt.figure(figsize=(8, 5))
    plt.plot(
        [result["tube_count"] for result in results],
        [100.0 * result["overall_co2_conversion"] for result in results],
        marker="o",
        linewidth=2,
    )
    plt.xlabel("Tube count [-]")
    plt.ylabel("Overall CO2 conversion [%]")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def main() -> None:
    base_case = load_design_case(INPUT_PATH)
    baseline_summary = json.loads(BASELINE_SUMMARY_PATH.read_text())
    fixed_stage_lengths_m = tuple(baseline_summary["sized_tube_lengths_m"])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, object]] = []
    for tube_count in TUBE_COUNTS:
        design_case = replace(
            base_case,
            reactor=replace(base_case.reactor, tube_count=tube_count),
            stages=replace(base_case.stages, tube_lengths_m=fixed_stage_lengths_m),
        )
        result, profile = simulate_with_profile(design_case)
        case_output_dir = OUTPUT_DIR / f"{tube_count}_tubes"
        case_output_dir.mkdir(parents=True, exist_ok=True)
        summary = {
            "tube_count": tube_count,
            "fixed_stage_lengths_m": list(fixed_stage_lengths_m),
            "minimum_gas_temperature_k": min(profile.gas_temperature_k),
            "maximum_gas_temperature_k": max(profile.gas_temperature_k),
            **result_to_dict(result),
        }
        (case_output_dir / "summary.json").write_text(json.dumps(summary, indent=2))
        _plot_temperature_profile(profile, case_output_dir / "temperature_profile.png")
        _plot_reaction_rate_profile(profile, case_output_dir / "reaction_rate_profile.png")
        results.append(summary)

    (OUTPUT_DIR / "summary.json").write_text(json.dumps(results, indent=2))
    _plot_conversion_sweep(results, OUTPUT_DIR / "co2_conversion_vs_tube_count.png")
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

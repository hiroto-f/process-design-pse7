"""Sweep coolant temperature while keeping four co-current stages within 8 m."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import matplotlib.pyplot as plt

from run_staged_reactor import _plot_reaction_rate_profile, _plot_temperature_profile
from reactor.staged_nonisothermal import load_design_case, result_to_dict, simulate_with_profile


PACKAGE_DIR = Path(__file__).parent
INPUT_PATH = PACKAGE_DIR / "inputs" / "four_stage_300c_to_400c_cocurrent.json"
OUTPUT_DIR = PACKAGE_DIR / "outputs" / "coolant_temperature_sweep_cocurrent"
MAX_TUBE_LENGTH_M = 8.0
MAX_SEARCH_LENGTH_M = 200.0
TARGET_OUTLET_TEMPERATURE_K = 673.15
COOLANT_TEMPERATURES_K = tuple(553.15 - 10.0 * index for index in range(7))


def _case_with_coolant_temperature(base_case, coolant_temperature_k: float):
    return replace(
        base_case,
        external_cooling=replace(
            base_case.external_cooling,
            coolant_inlet_temperature_k=coolant_temperature_k,
        ),
    )


def _find_minimum_tube_count_for_length_limit(base_case) -> tuple[int, tuple[float, ...]]:
    baseline_tube_count = base_case.reactor.tube_count
    while True:
        baseline_case = replace(
            base_case,
            reactor=replace(base_case.reactor, tube_count=baseline_tube_count),
        )
        try:
            baseline_lengths_m = _size_lengths(baseline_case)
            break
        except RuntimeError:
            baseline_tube_count *= 2
            if baseline_tube_count > 20000:
                raise
    estimated_tube_count = max(
        baseline_tube_count,
        int(
            -(-baseline_tube_count * max(baseline_lengths_m) // MAX_TUBE_LENGTH_M)
        ),
    )
    tube_count = estimated_tube_count
    while True:
        trial_case = replace(
            base_case,
            reactor=replace(base_case.reactor, tube_count=tube_count),
        )
        lengths_m = _size_lengths(trial_case)
        if max(lengths_m) <= MAX_TUBE_LENGTH_M:
            return tube_count, lengths_m
        tube_count += 1


def _stage_outlet_temperature(base_case, lengths_m, stage_index: int) -> float:
    result, _ = simulate_with_profile(
        replace(base_case, stages=replace(base_case.stages, tube_lengths_m=lengths_m))
    )
    return result.stages[stage_index].reactor_outlet_temperature_k


def _size_lengths(base_case) -> tuple[float, ...]:
    lengths = [0.0] * base_case.stages.count
    for stage_index in range(base_case.stages.count):
        lower = 0.0
        upper = 0.02
        while True:
            trial_lengths = tuple(
                lengths[index]
                if index < stage_index
                else upper
                if index == stage_index
                else 1.0e-9
                for index in range(base_case.stages.count)
            )
            outlet_temperature_k = _stage_outlet_temperature(
                base_case,
                trial_lengths,
                stage_index,
            )
            if outlet_temperature_k >= TARGET_OUTLET_TEMPERATURE_K:
                break
            upper *= 2.0
            if upper > MAX_SEARCH_LENGTH_M:
                raise RuntimeError(
                    f"stage {stage_index + 1} does not reach "
                    f"{TARGET_OUTLET_TEMPERATURE_K:.2f} K within "
                    f"{MAX_SEARCH_LENGTH_M:.2f} m"
                )
        for _ in range(40):
            midpoint = 0.5 * (lower + upper)
            trial_lengths = tuple(
                lengths[index]
                if index < stage_index
                else midpoint
                if index == stage_index
                else 1.0e-9
                for index in range(base_case.stages.count)
            )
            outlet_temperature_k = _stage_outlet_temperature(
                base_case,
                trial_lengths,
                stage_index,
            )
            if outlet_temperature_k >= TARGET_OUTLET_TEMPERATURE_K:
                upper = midpoint
            else:
                lower = midpoint
        lengths[stage_index] = upper
    return tuple(lengths)


def _plot_metric(results, key: str, ylabel: str, output_path: Path, multiplier: float = 1.0):
    plt.figure(figsize=(8, 5))
    plt.plot(
        [result["coolant_inlet_temperature_k"] - 273.15 for result in results],
        [multiplier * result[key] for result in results],
        marker="o",
        linewidth=2,
    )
    plt.xlabel("Coolant inlet temperature [degC]")
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
        case_output_dir = OUTPUT_DIR / f"{coolant_temperature_k:.2f}K"
        summary_path = case_output_dir / "summary.json"
        if summary_path.exists():
            results.append(json.loads(summary_path.read_text()))
            continue
        cooled_case = _case_with_coolant_temperature(base_case, coolant_temperature_k)
        tube_count, lengths_m = _find_minimum_tube_count_for_length_limit(cooled_case)
        design_case = replace(
            cooled_case,
            reactor=replace(cooled_case.reactor, tube_count=tube_count),
            stages=replace(cooled_case.stages, tube_lengths_m=lengths_m),
        )
        result, profile = simulate_with_profile(design_case)
        case_output_dir.mkdir(parents=True, exist_ok=True)
        summary = {
            "coolant_inlet_temperature_k": coolant_temperature_k,
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
        OUTPUT_DIR / "co2_conversion_vs_coolant_temperature.png",
        multiplier=100.0,
    )
    _plot_metric(
        results,
        "tube_count",
        "Minimum tube count [-]",
        OUTPUT_DIR / "tube_count_vs_coolant_temperature.png",
    )
    _plot_metric(
        results,
        "total_catalyst_mass_kg",
        "Total catalyst mass [kg]",
        OUTPUT_DIR / "catalyst_mass_vs_coolant_temperature.png",
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

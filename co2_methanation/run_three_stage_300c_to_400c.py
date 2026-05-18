"""Run three adiabatic stages sized from 300 C inlet to 400 C outlet."""

from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path

import matplotlib.pyplot as plt

from reactor.staged_nonisothermal import (
    DesignCase,
    ReactorProfile,
    load_design_case,
    result_to_dict,
    simulate_with_profile,
)


PACKAGE_DIR = Path(__file__).parent
INPUT_PATH = PACKAGE_DIR / "inputs" / "staged_reactor.json"
OUTPUT_DIR = PACKAGE_DIR / "outputs" / "three_stage_300c_to_400c"
TARGET_OUTLET_TEMPERATURE_K = 673.15
PLACEHOLDER_VOLUME_M3 = 1.0e-12


def _case_with_lengths(base_case: DesignCase, lengths_m: tuple[float, ...]) -> DesignCase:
    return replace(
        base_case,
        stages=replace(base_case.stages, tube_lengths_m=lengths_m),
    )


def _tube_cross_section_area_m2(base_case: DesignCase) -> float:
    diameter_m = base_case.reactor.tube_inner_diameter_m
    return math.pi * diameter_m**2 / 4.0


def _lengths_from_volumes(
    base_case: DesignCase,
    volumes_m3: tuple[float, ...],
) -> tuple[float, ...]:
    area_m2 = _tube_cross_section_area_m2(base_case)
    return tuple(volume_m3 / area_m2 for volume_m3 in volumes_m3)


def _stage_outlet_temperature(
    base_case: DesignCase,
    volumes_m3: tuple[float, ...],
    stage_index: int,
) -> float:
    lengths_m = _lengths_from_volumes(base_case, volumes_m3)
    result, _ = simulate_with_profile(_case_with_lengths(base_case, lengths_m))
    return result.stages[stage_index].reactor_outlet_temperature_k


def _size_volumes(base_case: DesignCase) -> tuple[float, ...]:
    volumes = [0.0] * base_case.stages.count
    for stage_index in range(base_case.stages.count):
        lower = 0.0
        upper = 1.0e-6
        while True:
            trial_volumes = tuple(
                volumes[index]
                if index < stage_index
                else upper
                if index == stage_index
                else PLACEHOLDER_VOLUME_M3
                for index in range(base_case.stages.count)
            )
            outlet_temperature_k = _stage_outlet_temperature(
                base_case,
                trial_volumes,
                stage_index,
            )
            if outlet_temperature_k >= TARGET_OUTLET_TEMPERATURE_K or upper >= 20.0:
                break
            upper *= 2.0
        if outlet_temperature_k < TARGET_OUTLET_TEMPERATURE_K:
            raise RuntimeError(
                f"stage {stage_index + 1} did not reach "
                f"{TARGET_OUTLET_TEMPERATURE_K:.2f} K within {upper:.6g} m3"
            )
        for _ in range(40):
            midpoint = 0.5 * (lower + upper)
            trial_volumes = tuple(
                volumes[index]
                if index < stage_index
                else midpoint
                if index == stage_index
                else PLACEHOLDER_VOLUME_M3
                for index in range(base_case.stages.count)
            )
            outlet_temperature_k = _stage_outlet_temperature(
                base_case,
                trial_volumes,
                stage_index,
            )
            if outlet_temperature_k >= TARGET_OUTLET_TEMPERATURE_K:
                upper = midpoint
            else:
                lower = midpoint
        volumes[stage_index] = upper
    return tuple(volumes)


def _cumulative_catalyst_volume_m3(
    base_case: DesignCase,
    profile: ReactorProfile,
) -> tuple[float, ...]:
    area_m2 = _tube_cross_section_area_m2(base_case)
    return tuple(position_m * area_m2 for position_m in profile.axial_position_m)


def _plot_temperature_profile_by_volume(
    base_case: DesignCase,
    profile: ReactorProfile,
    output_path: Path,
) -> None:
    catalyst_volume_m3 = _cumulative_catalyst_volume_m3(base_case, profile)
    plt.figure(figsize=(8, 5))
    plt.plot(catalyst_volume_m3, profile.gas_temperature_k, linewidth=2)
    boundaries = [
        catalyst_volume_m3[index]
        for index in range(1, len(profile.stage_index))
        if profile.stage_index[index] != profile.stage_index[index - 1]
    ]
    for boundary_m3 in boundaries:
        plt.axvline(boundary_m3, color="0.6", linestyle="--", linewidth=1)
    plt.xlabel("Cumulative catalyst volume [m3]")
    plt.ylabel("Gas temperature [K]")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def _plot_reaction_rate_profile_by_volume(
    base_case: DesignCase,
    profile: ReactorProfile,
    output_path: Path,
) -> None:
    catalyst_volume_m3 = _cumulative_catalyst_volume_m3(base_case, profile)
    plt.figure(figsize=(8, 5))
    labels = {
        "R1": "R1: reforming",
        "R2": "R2: water-gas shift",
        "R3": "R3: overall reforming",
    }
    for reaction_name, values in profile.reaction_rates_kmol_per_kgcat_h.items():
        plt.plot(
            catalyst_volume_m3,
            values,
            linewidth=2,
            label=labels[reaction_name],
        )
    boundaries = [
        catalyst_volume_m3[index]
        for index in range(1, len(profile.stage_index))
        if profile.stage_index[index] != profile.stage_index[index - 1]
    ]
    for boundary_m3 in boundaries:
        plt.axvline(boundary_m3, color="0.6", linestyle="--", linewidth=1)
    plt.xlabel("Cumulative catalyst volume [m3]")
    plt.ylabel("Reaction rate [kmol/(kgcat h)]")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=180)
    plt.close()


def main() -> None:
    base_case = load_design_case(INPUT_PATH)
    volumes_m3 = _size_volumes(base_case)
    lengths_m = _lengths_from_volumes(base_case, volumes_m3)
    design_case = _case_with_lengths(base_case, lengths_m)
    result, profile = simulate_with_profile(design_case)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "stage_inlet_temperature_k": base_case.feed_temperature_k,
        "target_outlet_temperature_k": TARGET_OUTLET_TEMPERATURE_K,
        "sized_catalyst_volumes_m3": list(volumes_m3),
        "sized_tube_lengths_m": list(lengths_m),
        **result_to_dict(result),
    }
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    _plot_temperature_profile_by_volume(
        base_case,
        profile,
        OUTPUT_DIR / "temperature_profile.png",
    )
    _plot_reaction_rate_profile_by_volume(
        base_case,
        profile,
        OUTPUT_DIR / "reaction_rate_profile.png",
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

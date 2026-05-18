"""Size a four-stage adiabatic Xu case to the temperatures from multi_reactors.pdf."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from run_staged_reactor import _plot_reaction_rate_profile, _plot_temperature_profile
from reactor.staged_nonisothermal import (
    DesignCase,
    load_design_case,
    result_to_dict,
    simulate_with_profile,
)


PACKAGE_DIR = Path(__file__).parent
INPUT_PATH = PACKAGE_DIR / "inputs" / "multi_reactors_4stage.json"
OUTPUT_DIR = PACKAGE_DIR / "outputs" / "multi_reactors_4stage_target_temperature"
TARGET_OUTLET_TEMPERATURES_K = (871.8722222222221, 747.3722222222223, 666.7611111111111, 662.3722222222223)
PLACEHOLDER_LENGTH_M = 1.0e-9


def _case_with_lengths(base_case: DesignCase, lengths_m: tuple[float, ...]) -> DesignCase:
    return replace(
        base_case,
        stages=replace(base_case.stages, tube_lengths_m=lengths_m),
    )


def _stage_outlet_temperature(base_case: DesignCase, lengths_m: tuple[float, ...], stage_index: int) -> float:
    result, _ = simulate_with_profile(_case_with_lengths(base_case, lengths_m))
    return result.stages[stage_index].reactor_outlet_temperature_k


def _size_lengths(base_case: DesignCase) -> tuple[float, ...]:
    lengths = [0.0, 0.0, 0.0, 0.0]
    for stage_index, target_temperature_k in enumerate(TARGET_OUTLET_TEMPERATURES_K):
        lower = 0.0
        upper = 0.05
        while True:
            trial_lengths = tuple(
                lengths[index]
                if index < stage_index
                else upper
                if index == stage_index
                else PLACEHOLDER_LENGTH_M
                for index in range(4)
            )
            outlet_temperature_k = _stage_outlet_temperature(
                base_case,
                trial_lengths,
                stage_index,
            )
            if outlet_temperature_k >= target_temperature_k or upper >= 20.0:
                break
            upper *= 2.0
        for _ in range(40):
            midpoint = 0.5 * (lower + upper)
            trial_lengths = tuple(
                lengths[index]
                if index < stage_index
                else midpoint
                if index == stage_index
                else PLACEHOLDER_LENGTH_M
                for index in range(4)
            )
            outlet_temperature_k = _stage_outlet_temperature(
                base_case,
                trial_lengths,
                stage_index,
            )
            if outlet_temperature_k >= target_temperature_k:
                upper = midpoint
            else:
                lower = midpoint
        lengths[stage_index] = upper
    return tuple(lengths)


def main() -> None:
    base_case = load_design_case(INPUT_PATH)
    lengths_m = _size_lengths(base_case)
    design_case = _case_with_lengths(base_case, lengths_m)
    result, profile = simulate_with_profile(design_case)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "target_outlet_temperatures_k": list(TARGET_OUTLET_TEMPERATURES_K),
        "sized_tube_lengths_m": list(lengths_m),
        **result_to_dict(result),
    }
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    _plot_temperature_profile(profile, OUTPUT_DIR / "temperature_profile.png")
    _plot_reaction_rate_profile(profile, OUTPUT_DIR / "reaction_rate_profile.png")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

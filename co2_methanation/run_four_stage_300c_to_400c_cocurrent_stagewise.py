"""Run four wall-cooled stages with stagewise coolant inlet temperatures."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from run_four_stage_300c_to_400c_cocurrent import _size_lengths
from run_staged_reactor import _plot_reaction_rate_profile, _plot_temperature_profile
from reactor.staged_nonisothermal import DesignCase, load_design_case, result_to_dict, simulate_with_profile


PACKAGE_DIR = Path(__file__).parent
INPUT_PATH = PACKAGE_DIR / "inputs" / "four_stage_300c_to_400c_cocurrent_stagewise.json"
OUTPUT_DIR = PACKAGE_DIR / "outputs" / "four_stage_300c_to_400c_cocurrent_stagewise"
TARGET_OUTLET_TEMPERATURE_K = 673.15


def _case_with_lengths(base_case: DesignCase, lengths_m: tuple[float, ...]) -> DesignCase:
    return replace(
        base_case,
        stages=replace(base_case.stages, tube_lengths_m=lengths_m),
    )


def main() -> None:
    base_case = load_design_case(INPUT_PATH)
    lengths_m = _size_lengths(base_case)
    design_case = _case_with_lengths(base_case, lengths_m)
    result, profile = simulate_with_profile(design_case)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "target_outlet_temperature_k": TARGET_OUTLET_TEMPERATURE_K,
        "sized_tube_lengths_m": list(lengths_m),
        "coolant_inlet_temperatures_k": list(
            design_case.external_cooling.coolant_inlet_temperatures_k
            if design_case.external_cooling and design_case.external_cooling.coolant_inlet_temperatures_k
            else []
        ),
        **result_to_dict(result),
    }
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    _plot_temperature_profile(profile, OUTPUT_DIR / "temperature_profile.png")
    _plot_reaction_rate_profile(profile, OUTPUT_DIR / "reaction_rate_profile.png")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

"""Run the four-stage adiabatic case based on multi_reactors.pdf."""

from __future__ import annotations

import json
from pathlib import Path

from run_staged_reactor import _plot_reaction_rate_profile, _plot_temperature_profile
from reactor.staged_nonisothermal import load_design_case, result_to_dict, simulate_with_profile


PACKAGE_DIR = Path(__file__).parent
INPUT_PATH = PACKAGE_DIR / "inputs" / "multi_reactors_4stage.json"
OUTPUT_DIR = PACKAGE_DIR / "outputs" / "multi_reactors_4stage"


def main() -> None:
    result, profile = simulate_with_profile(load_design_case(INPUT_PATH))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = result_to_dict(result)
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2))
    _plot_temperature_profile(profile, OUTPUT_DIR / "temperature_profile.png")
    _plot_reaction_rate_profile(profile, OUTPUT_DIR / "reaction_rate_profile.png")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

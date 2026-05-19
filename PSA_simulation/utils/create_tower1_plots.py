from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

from PSA_simulation.utils import (
    plot_adsorption_hydrogen_concentration,
    plot_adsorption_methane_concentration,
    plot_desorption_methane_loading,
)


DEFAULT_TOWER1_OUTPUT_DIR = Path("PSA_simulation/outputs/tower_1")


def create_tower1_plots(
    tower_output_dir: str | Path = DEFAULT_TOWER1_OUTPUT_DIR,
) -> list[Path]:
    """Create the standard three profile plots from tower_1 output CSV files."""

    output_dir = Path(tower_output_dir)
    _set_matplotlib_config_dir(output_dir)

    adsorption_profile = output_dir / "adsorption_1_profile.csv"
    desorption_profile = output_dir / "desorption_profile.csv"

    output_paths = [
        output_dir / "adsorption_h2_concentration.png",
        output_dir / "adsorption_ch4_concentration.png",
        output_dir / "desorption_ch4_loading.png",
    ]

    plot_adsorption_hydrogen_concentration(adsorption_profile, output_paths[0])
    plot_adsorption_methane_concentration(adsorption_profile, output_paths[1])
    plot_desorption_methane_loading(desorption_profile, output_paths[2])

    return output_paths


def _set_matplotlib_config_dir(output_dir: Path) -> None:
    if "MPLCONFIGDIR" not in os.environ:
        os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="psa-matplotlib-")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create tower_1 PSA profile plots.")
    parser.add_argument(
        "--tower-output-dir",
        type=Path,
        default=DEFAULT_TOWER1_OUTPUT_DIR,
        help="Directory containing tower_1 profile CSV files.",
    )
    args = parser.parse_args()

    output_paths = create_tower1_plots(args.tower_output_dir)
    for output_path in output_paths:
        print(f"Output written to: {output_path}")


if __name__ == "__main__":
    main()

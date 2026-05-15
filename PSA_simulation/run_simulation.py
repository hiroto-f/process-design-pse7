from __future__ import annotations

import argparse
from pathlib import Path

from .preprocess import Preprocessor
from .simulator import PsaSimulator
from .structured_io import load_common_inputs, load_tower_input, save_outputs


def find_tower_paths(tower_input_dir: Path, tower_name: str | None = None) -> list[Path]:
    if not tower_input_dir.exists():
        return []
    if tower_name is not None:
        tower_path = tower_input_dir / tower_name
        if tower_path.suffix != ".json":
            tower_path = tower_path.with_suffix(".json")
        return [tower_path] if tower_path.is_file() else []
    return sorted(path for path in tower_input_dir.glob("*.json") if path.is_file())


def run_one_tower(inputs, output_dir: Path, tower_name: str, setup_only: bool, max_steps: int | None) -> None:
    setup_state = Preprocessor(inputs).run()
    simulation_state = None
    if not setup_only:
        simulation_state = PsaSimulator(inputs, setup_state, max_steps=max_steps).run()
    save_outputs(inputs, output_dir, tower_name, setup_state, simulation_state)
    print(f"Output written to: {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the PSA model using JSON input and CSV/JSON output.")
    parser.add_argument("--input-dir", type=Path, default=Path("PSA_simulation/inputs/common"), help="Common JSON directory.")
    parser.add_argument(
        "--tower-input-dir",
        type=Path,
        default=Path("PSA_simulation/inputs/towers"),
        help="Directory containing one JSON file per tower.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("PSA_simulation/outputs"))
    parser.add_argument(
        "--tower",
        help="Run only one tower JSON file by stem or filename, for example tower_2 or tower_2.json.",
    )
    parser.add_argument("--max-steps", type=int, default=None, help="Debug safety limit per adsorption/desorption step.")
    parser.add_argument("--setup-only", action="store_true", help="Only run the setup calculations.")
    args = parser.parse_args()

    adsorbent, components = load_common_inputs(args.input_dir)
    tower_paths = find_tower_paths(args.tower_input_dir, args.tower)
    if not tower_paths:
        if args.tower:
            raise FileNotFoundError(f"Tower JSON file not found: {args.tower_input_dir / args.tower}")
        raise FileNotFoundError(f"No tower JSON files found in {args.tower_input_dir}")

    for tower_path in tower_paths:
        tower_name = tower_path.stem
        print(f"Running tower: {tower_name}")
        inputs = load_tower_input(tower_path, adsorbent, components)
        run_one_tower(inputs, args.output_dir / tower_name, tower_name, args.setup_only, args.max_steps)


if __name__ == "__main__":
    main()

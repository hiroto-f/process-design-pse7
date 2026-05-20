from __future__ import annotations

import argparse
from pathlib import Path

from .simulators import FastPsaSimulator
from .preprocess import Preprocessor
from .structured_io import load_common_inputs, load_tower_input, save_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a coarse PSA simulation for quick screening.")
    parser.add_argument("--input-dir", type=Path, default=Path("PSA_simulation/inputs/common"))
    parser.add_argument("--tower-input", type=Path, default=Path("PSA_simulation/inputs/towers/tower_1.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("PSA_simulation/outputs/fastmode"))
    parser.add_argument("--grid-size", type=int, default=50)
    parser.add_argument("--adsorption-dt", type=float, default=0.00002)
    parser.add_argument("--desorption-dt", type=float, default=0.000005)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--save-profiles", action="store_true")
    args = parser.parse_args()

    adsorbent, components = load_common_inputs(args.input_dir)
    inputs = load_tower_input(args.tower_input, adsorbent, components)
    setup_state = Preprocessor(inputs).run()
    simulation_state = FastPsaSimulator(
        inputs,
        setup_state,
        max_steps=args.max_steps,
        grid_size=args.grid_size,
        adsorption_dt=args.adsorption_dt,
        desorption_dt=args.desorption_dt,
        cycles=args.cycles,
        save_profiles=args.save_profiles,
    ).run()
    save_outputs(inputs, args.output_dir, args.tower_input.stem, setup_state, simulation_state)
    print(f"Fastmode output written to: {args.output_dir}")


if __name__ == "__main__":
    main()

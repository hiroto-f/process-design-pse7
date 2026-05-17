"""Couple catalyst-mass sizing with tube-count selection."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from pathlib import Path

from reaction_Champon.champon_reactor import (
    DEFAULT_INPUT_PATH,
    DesignCase,
    ReactorConfig,
    temperature_profile_for_full_bed,
    validate_profile_temperature_range,
)
from reaction_Champon.utils.catalyst_mass_sizing import size_for_target_conversion
from reaction_Champon.utils.tube_sizing import (
    TubeSizingResult,
    select_tube_count_for_catalyst_mass,
)


@dataclass(frozen=True)
class CoupledTubeSizingIteration:
    iteration: int
    tube_count: int
    required_catalyst_mass_kg: float
    achieved_conversion: float
    next_tube_count: int


@dataclass(frozen=True)
class CoupledTubeSizingResult:
    converged: bool
    iterations: tuple[CoupledTubeSizingIteration, ...]
    tube_sizing: TubeSizingResult
    required_catalyst_mass_kg: float
    achieved_conversion: float
    temperature_range_valid: bool
    min_gas_temperature_k: float
    max_gas_temperature_k: float


def solve_coupled_tube_sizing(
    design_case: DesignCase,
    temperature_k: float,
    initial_tube_count: int | None = None,
    max_catalyst_mass_kg: float | None = None,
    max_iterations: int = 25,
) -> CoupledTubeSizingResult:
    """Iterate tube count and catalyst-mass sizing until tube count is consistent."""
    if max_iterations <= 0:
        raise ValueError("max_iterations must be positive")

    tube_count = initial_tube_count if initial_tube_count is not None else design_case.tube_count
    if tube_count <= 0:
        raise ValueError("initial_tube_count must be positive")

    iterations: list[CoupledTubeSizingIteration] = []
    final_tube_sizing: TubeSizingResult | None = None
    final_required_mass_kg: float | None = None
    final_achieved_conversion: float | None = None

    for iteration in range(1, max_iterations + 1):
        current_case = replace(design_case, tube_count=tube_count)
        search_limit_kg = (
            max_catalyst_mass_kg
            if max_catalyst_mass_kg is not None
            else current_case.sizing.max_catalyst_mass_kg
        )
        sizing = size_for_target_conversion(
            design_case=current_case,
            config=ReactorConfig(
                temperature_k=temperature_k,
                pressure_bar=current_case.pressure_bar,
                integration_steps=current_case.integration_steps,
            ),
            target_conversion=current_case.sizing.target_conversion,
            max_catalyst_mass_kg=search_limit_kg,
        )
        if sizing.catalyst_mass_kg is None:
            raise ValueError("target conversion is not reachable within max catalyst mass")

        tube_sizing = select_tube_count_for_catalyst_mass(
            required_catalyst_mass_kg=sizing.catalyst_mass_kg,
            catalyst_bulk_density_kg_per_m3=current_case.catalyst_bulk_density_kg_per_m3,
            tube_inner_diameter_m=current_case.tube_inner_diameter_m,
            tube_length_m=current_case.tube_length_m,
        )
        iterations.append(
            CoupledTubeSizingIteration(
                iteration=iteration,
                tube_count=tube_count,
                required_catalyst_mass_kg=sizing.catalyst_mass_kg,
                achieved_conversion=sizing.achieved_conversion,
                next_tube_count=tube_sizing.tube_count,
            )
        )
        final_tube_sizing = tube_sizing
        final_required_mass_kg = sizing.catalyst_mass_kg
        final_achieved_conversion = sizing.achieved_conversion

        if tube_sizing.tube_count == tube_count:
            converged_case = replace(current_case, tube_count=tube_sizing.tube_count)
            profile = temperature_profile_for_full_bed(converged_case, temperature_k)
            min_gas_temperature_k = min(profile.gas_temperature_k)
            max_gas_temperature_k = max(profile.gas_temperature_k)
            return CoupledTubeSizingResult(
                converged=True,
                iterations=tuple(iterations),
                tube_sizing=tube_sizing,
                required_catalyst_mass_kg=final_required_mass_kg,
                achieved_conversion=final_achieved_conversion,
                temperature_range_valid=(
                    min_gas_temperature_k >= 623.0 and max_gas_temperature_k <= 723.0
                ),
                min_gas_temperature_k=min_gas_temperature_k,
                max_gas_temperature_k=max_gas_temperature_k,
            )

        tube_count = tube_sizing.tube_count

    assert final_tube_sizing is not None
    assert final_required_mass_kg is not None
    assert final_achieved_conversion is not None
    return CoupledTubeSizingResult(
        converged=False,
        iterations=tuple(iterations),
        tube_sizing=final_tube_sizing,
        required_catalyst_mass_kg=final_required_mass_kg,
        achieved_conversion=final_achieved_conversion,
        temperature_range_valid=False,
        min_gas_temperature_k=float("nan"),
        max_gas_temperature_k=float("nan"),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Iterate catalyst-mass sizing and tube-count selection to consistency."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--temperature-k", type=float, required=True)
    parser.add_argument("--initial-tube-count", type=int)
    parser.add_argument("--max-catalyst-mass-kg", type=float)
    parser.add_argument("--max-iterations", type=int, default=25)
    return parser.parse_args()


def main() -> None:
    from reaction_Champon.champon_reactor import load_design_case

    args = parse_args()
    design_case = load_design_case(args.input)
    result = solve_coupled_tube_sizing(
        design_case=design_case,
        temperature_k=args.temperature_k,
        initial_tube_count=args.initial_tube_count,
        max_catalyst_mass_kg=args.max_catalyst_mass_kg,
        max_iterations=args.max_iterations,
    )
    for item in result.iterations:
        print(
            f"iteration={item.iteration} "
            f"tube_count={item.tube_count} "
            f"required_catalyst_mass_kg={item.required_catalyst_mass_kg:.12g} "
            f"achieved_conversion={item.achieved_conversion:.12g} "
            f"next_tube_count={item.next_tube_count}"
        )
    print(f"converged={result.converged}")
    print(f"tube_count={result.tube_sizing.tube_count}")
    print(f"required_catalyst_mass_kg={result.required_catalyst_mass_kg:.12g}")
    print(f"available_catalyst_mass_kg={result.tube_sizing.available_catalyst_mass_kg:.12g}")
    print(f"catalyst_utilization_fraction={result.tube_sizing.catalyst_utilization_fraction:.12g}")
    print(f"temperature_range_valid={result.temperature_range_valid}")
    print(f"min_gas_temperature_k={result.min_gas_temperature_k:.12g}")
    print(f"max_gas_temperature_k={result.max_gas_temperature_k:.12g}")


if __name__ == "__main__":
    main()

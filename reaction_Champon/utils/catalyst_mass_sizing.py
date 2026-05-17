"""Calculate catalyst mass required for a target conversion."""

from __future__ import annotations

import argparse
from pathlib import Path

from reaction_Champon.champon_reactor import (
    DEFAULT_INPUT_PATH,
    DesignCase,
    ReactorConfig,
    SizingResult,
    load_design_case,
    simulate_fixed_bed,
)


def size_for_target_conversion(
    design_case: DesignCase,
    config: ReactorConfig,
    target_conversion: float,
    max_catalyst_mass_kg: float,
    tolerance: float = 1.0e-4,
) -> SizingResult:
    """Size catalyst mass for a target conversion by bisection."""
    if not 0.0 < target_conversion < 1.0:
        raise ValueError("target_conversion must lie between 0 and 1")
    if max_catalyst_mass_kg <= 0.0:
        raise ValueError("max_catalyst_mass_kg must be positive")

    upper = simulate_fixed_bed(design_case, config, max_catalyst_mass_kg)
    if upper.target_conversion < target_conversion:
        return SizingResult(
            temperature_k=config.temperature_k,
            target_conversion=target_conversion,
            reached_target=False,
            catalyst_mass_kg=None,
            catalyst_mass_per_tube_kg=None,
            search_limit_kg=max_catalyst_mass_kg,
            search_limit_per_tube_kg=max_catalyst_mass_kg / design_case.tube_count,
            achieved_conversion=upper.target_conversion,
            outlet_flows_kmol_per_h=upper.outlet_flows_kmol_per_h,
            outlet_flows_per_tube_kmol_per_h=upper.outlet_flows_per_tube_kmol_per_h,
            ch4_yield_on_co2_feed=upper.ch4_yield_on_co2_feed,
            co_yield_on_co2_feed=upper.co_yield_on_co2_feed,
            ch4_selectivity_on_converted_co2=upper.ch4_selectivity_on_converted_co2,
            co_selectivity_on_converted_co2=upper.co_selectivity_on_converted_co2,
            gas_outlet_temperature_k=upper.gas_outlet_temperature_k,
            max_gas_temperature_k=upper.max_gas_temperature_k,
            coolant_outlet_temperature_k=upper.coolant_outlet_temperature_k,
            cooling_duty_kj_per_h=upper.cooling_duty_kj_per_h,
        )

    lower_mass = 0.0
    upper_mass = max_catalyst_mass_kg
    best = upper
    for _ in range(40):
        mid_mass = 0.5 * (lower_mass + upper_mass)
        mid = simulate_fixed_bed(design_case, config, mid_mass)
        best = mid
        error = mid.target_conversion - target_conversion
        if abs(error) <= tolerance:
            break
        if error < 0.0:
            lower_mass = mid_mass
        else:
            upper_mass = mid_mass

    return SizingResult(
        temperature_k=config.temperature_k,
        target_conversion=target_conversion,
        reached_target=True,
        catalyst_mass_kg=best.catalyst_mass_kg,
        catalyst_mass_per_tube_kg=best.catalyst_mass_per_tube_kg,
        search_limit_kg=max_catalyst_mass_kg,
        search_limit_per_tube_kg=max_catalyst_mass_kg / design_case.tube_count,
        achieved_conversion=best.target_conversion,
        outlet_flows_kmol_per_h=best.outlet_flows_kmol_per_h,
        outlet_flows_per_tube_kmol_per_h=best.outlet_flows_per_tube_kmol_per_h,
        ch4_yield_on_co2_feed=best.ch4_yield_on_co2_feed,
        co_yield_on_co2_feed=best.co_yield_on_co2_feed,
        ch4_selectivity_on_converted_co2=best.ch4_selectivity_on_converted_co2,
        co_selectivity_on_converted_co2=best.co_selectivity_on_converted_co2,
        gas_outlet_temperature_k=best.gas_outlet_temperature_k,
        max_gas_temperature_k=best.max_gas_temperature_k,
        coolant_outlet_temperature_k=best.coolant_outlet_temperature_k,
        cooling_duty_kj_per_h=best.cooling_duty_kj_per_h,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Calculate catalyst mass required to reach a target conversion."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        help="Path to the reactor-design JSON input file.",
    )
    parser.add_argument(
        "--temperature-k",
        type=float,
        required=True,
        help="Gas inlet temperature in K.",
    )
    parser.add_argument(
        "--target-conversion",
        type=float,
        help="Target conversion as a fraction. Defaults to sizing.target_conversion from input.",
    )
    parser.add_argument(
        "--max-catalyst-mass-kg",
        type=float,
        help="Search upper bound in kg. Defaults to sizing.max_catalyst_mass_kg from input.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    design_case = load_design_case(args.input)
    target_conversion = (
        args.target_conversion
        if args.target_conversion is not None
        else design_case.sizing.target_conversion
    )
    max_catalyst_mass_kg = (
        args.max_catalyst_mass_kg
        if args.max_catalyst_mass_kg is not None
        else design_case.sizing.max_catalyst_mass_kg
    )
    result = size_for_target_conversion(
        design_case=design_case,
        config=ReactorConfig(
            temperature_k=args.temperature_k,
            pressure_bar=design_case.pressure_bar,
            integration_steps=design_case.integration_steps,
        ),
        target_conversion=target_conversion,
        max_catalyst_mass_kg=max_catalyst_mass_kg,
    )

    print(f"inlet_temperature_k={result.temperature_k:g}")
    print(f"target_conversion={result.target_conversion:g}")
    print(f"reached_target={result.reached_target}")
    if result.catalyst_mass_kg is None:
        print(f"required_catalyst_mass_kg=>{result.search_limit_kg:g}")
    else:
        print(f"required_catalyst_mass_kg={result.catalyst_mass_kg:.12g}")
        print(f"required_catalyst_mass_per_tube_kg={result.catalyst_mass_per_tube_kg:.12g}")
    print(f"achieved_conversion={result.achieved_conversion:.12g}")


if __name__ == "__main__":
    main()

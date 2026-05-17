"""Determine tube count from catalyst mass and selected tube geometry."""

from __future__ import annotations

import argparse
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class TubeSizingResult:
    required_catalyst_mass_kg: float
    catalyst_bulk_density_kg_per_m3: float
    tube_inner_diameter_m: float
    tube_length_m: float
    tube_cross_section_area_m2: float
    catalyst_capacity_per_tube_kg: float
    tube_count: int
    available_catalyst_mass_kg: float
    excess_catalyst_capacity_kg: float
    catalyst_utilization_fraction: float


def select_tube_count_for_catalyst_mass(
    required_catalyst_mass_kg: float,
    catalyst_bulk_density_kg_per_m3: float,
    tube_inner_diameter_m: float,
    tube_length_m: float,
) -> TubeSizingResult:
    """Return the tube count required for a selected tube diameter and length."""
    if required_catalyst_mass_kg <= 0.0:
        raise ValueError("required_catalyst_mass_kg must be positive")
    if catalyst_bulk_density_kg_per_m3 <= 0.0:
        raise ValueError("catalyst_bulk_density_kg_per_m3 must be positive")
    if tube_inner_diameter_m <= 0.0:
        raise ValueError("tube_inner_diameter_m must be positive")
    if tube_length_m <= 0.0:
        raise ValueError("tube_length_m must be positive")

    tube_cross_section_area_m2 = math.pi * tube_inner_diameter_m**2 / 4.0
    catalyst_capacity_per_tube_kg = (
        catalyst_bulk_density_kg_per_m3 * tube_cross_section_area_m2 * tube_length_m
    )
    tube_count = math.ceil(required_catalyst_mass_kg / catalyst_capacity_per_tube_kg)
    available_catalyst_mass_kg = tube_count * catalyst_capacity_per_tube_kg
    excess_catalyst_capacity_kg = available_catalyst_mass_kg - required_catalyst_mass_kg
    catalyst_utilization_fraction = required_catalyst_mass_kg / available_catalyst_mass_kg
    return TubeSizingResult(
        required_catalyst_mass_kg=required_catalyst_mass_kg,
        catalyst_bulk_density_kg_per_m3=catalyst_bulk_density_kg_per_m3,
        tube_inner_diameter_m=tube_inner_diameter_m,
        tube_length_m=tube_length_m,
        tube_cross_section_area_m2=tube_cross_section_area_m2,
        catalyst_capacity_per_tube_kg=catalyst_capacity_per_tube_kg,
        tube_count=tube_count,
        available_catalyst_mass_kg=available_catalyst_mass_kg,
        excess_catalyst_capacity_kg=excess_catalyst_capacity_kg,
        catalyst_utilization_fraction=catalyst_utilization_fraction,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Determine tube count from required catalyst mass and selected geometry."
    )
    parser.add_argument("--required-catalyst-mass-kg", type=float, required=True)
    parser.add_argument("--catalyst-bulk-density-kg-per-m3", type=float, required=True)
    parser.add_argument("--tube-inner-diameter-m", type=float, required=True)
    parser.add_argument("--tube-length-m", type=float, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = select_tube_count_for_catalyst_mass(
        required_catalyst_mass_kg=args.required_catalyst_mass_kg,
        catalyst_bulk_density_kg_per_m3=args.catalyst_bulk_density_kg_per_m3,
        tube_inner_diameter_m=args.tube_inner_diameter_m,
        tube_length_m=args.tube_length_m,
    )
    print(f"tube_count={result.tube_count}")
    print(f"catalyst_capacity_per_tube_kg={result.catalyst_capacity_per_tube_kg:.12g}")
    print(f"available_catalyst_mass_kg={result.available_catalyst_mass_kg:.12g}")
    print(f"excess_catalyst_capacity_kg={result.excess_catalyst_capacity_kg:.12g}")
    print(f"catalyst_utilization_fraction={result.catalyst_utilization_fraction:.12g}")


if __name__ == "__main__":
    main()

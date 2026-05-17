from __future__ import annotations

import unittest
from pathlib import Path

from reaction_Champon.champon_reactor import (
    ReactorConfig,
    build_summary,
    equilibrium_constant,
    load_design_case,
    partial_pressures,
    reaction_rates_kmol_per_kgcat_h,
    size_for_target_conversion,
    simulate_fixed_bed,
    temperature_profile_for_result,
    temperature_profile_for_full_bed,
    validate_profile_temperature_range,
    write_reaction_rate_profile_by_position_image,
    write_reaction_rate_profile_image,
    write_temperature_profile_by_position_image,
    write_temperature_profile_image,
)


INPUT_PATH = Path(__file__).parent / "inputs" / "input.json"


class ChamponReactorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.design_case = load_design_case(INPUT_PATH)

    def test_three_reactions_are_loaded(self) -> None:
        self.assertEqual(
            [reaction.name for reaction in self.design_case.reactions],
            ["CO2 methanation", "reverse water-gas shift", "CO methanation"],
        )

    def test_champon_constants_are_loaded(self) -> None:
        self.assertEqual(set(self.design_case.kinetics.adsorption_constants), {"CO", "H2O", "CO2", "H2"})
        self.assertAlmostEqual(
            self.design_case.kinetics.kinetic_constants["CO2 methanation"].activation_energy_kj_per_mol,
            110.0,
        )

    def test_partial_pressures_follow_feed_ratio(self) -> None:
        pressures = partial_pressures(
            self.design_case.feed.flows_kmol_per_h,
            total_pressure_bar=1.0,
        )
        self.assertAlmostEqual(pressures["CO2"], 0.2)
        self.assertAlmostEqual(pressures["H2"], 0.8)

    def test_equilibrium_constants_are_positive(self) -> None:
        for reaction in self.design_case.reactions:
            self.assertGreater(equilibrium_constant(reaction.stoichiometry, 673.0), 0.0)

    def test_all_reaction_rates_are_available(self) -> None:
        rates = reaction_rates_kmol_per_kgcat_h(
            self.design_case.feed.flows_kmol_per_h,
            ReactorConfig(
                temperature_k=673.0,
                pressure_bar=self.design_case.pressure_bar,
                integration_steps=self.design_case.integration_steps,
            ),
            self.design_case.reactions,
            self.design_case.kinetics,
        )
        self.assertEqual(set(rates), {reaction.name for reaction in self.design_case.reactions})

    def test_zero_catalyst_mass_keeps_feed_unchanged(self) -> None:
        result = simulate_fixed_bed(
            design_case=self.design_case,
            config=ReactorConfig(
                temperature_k=673.0,
                pressure_bar=self.design_case.pressure_bar,
                integration_steps=self.design_case.integration_steps,
            ),
            catalyst_mass_kg=0.0,
        )
        self.assertEqual(result.outlet_flows_kmol_per_h, self.design_case.feed.flows_kmol_per_h)

    def test_countercurrent_cooling_warms_the_coolant(self) -> None:
        result = simulate_fixed_bed(
            design_case=self.design_case,
            config=ReactorConfig(
                temperature_k=673.0,
                pressure_bar=self.design_case.pressure_bar,
                integration_steps=self.design_case.integration_steps,
            ),
            catalyst_mass_kg=0.2,
        )
        self.assertGreater(
            result.coolant_outlet_temperature_k,
            self.design_case.thermal.countercurrent_cooling.coolant_inlet_temperature_k,
        )

    def test_summary_contains_results(self) -> None:
        result = size_for_target_conversion(
            design_case=self.design_case,
            config=ReactorConfig(
                temperature_k=673.0,
                pressure_bar=self.design_case.pressure_bar,
                integration_steps=self.design_case.integration_steps,
            ),
            target_conversion=self.design_case.sizing.target_conversion,
            max_catalyst_mass_kg=self.design_case.sizing.max_catalyst_mass_kg,
        )
        summary = build_summary(self.design_case, [result])
        self.assertEqual(summary["basis"]["kinetic_model"], "Champon et al. (2019)")
        self.assertEqual(summary["basis"]["tube_count"], 100)
        self.assertEqual(summary["basis"]["tube_inner_diameter_m"], 0.02)
        self.assertAlmostEqual(
            summary["basis"]["available_total_catalyst_mass_kg"],
            50.2654824574367,
        )

    def test_profile_images_are_written(self) -> None:
        result = size_for_target_conversion(
            design_case=self.design_case,
            config=ReactorConfig(
                temperature_k=673.0,
                pressure_bar=self.design_case.pressure_bar,
                integration_steps=self.design_case.integration_steps,
            ),
            target_conversion=self.design_case.sizing.target_conversion,
            max_catalyst_mass_kg=self.design_case.sizing.max_catalyst_mass_kg,
        )
        profile = temperature_profile_for_result(self.design_case, result)
        temperature_path = Path("/private/tmp/test_champon_temperature_profile.png")
        rate_path = Path("/private/tmp/test_champon_reaction_rate_profile.png")
        position_temperature_path = Path("/private/tmp/test_champon_temperature_profile_z.png")
        position_rate_path = Path("/private/tmp/test_champon_reaction_rate_profile_z.png")
        write_temperature_profile_image(temperature_path, profile)
        write_reaction_rate_profile_image(rate_path, profile)
        write_temperature_profile_by_position_image(position_temperature_path, profile)
        write_reaction_rate_profile_by_position_image(position_rate_path, profile)
        self.assertGreater(temperature_path.stat().st_size, 0)
        self.assertGreater(rate_path.stat().st_size, 0)
        self.assertGreater(position_temperature_path.stat().st_size, 0)
        self.assertGreater(position_rate_path.stat().st_size, 0)
        self.assertEqual(profile.reactor_coordinate_m[0], 0.0)
        self.assertGreater(profile.reactor_coordinate_m[-1], 0.0)

    def test_full_bed_profile_spans_tube_length(self) -> None:
        profile = temperature_profile_for_full_bed(self.design_case, 673.0)
        self.assertAlmostEqual(profile.reactor_coordinate_m[-1], 2.0)

    def test_full_bed_profiles_stay_in_champon_temperature_range(self) -> None:
        for temperature_k in (623.0, 648.0, 673.0):
            profile = temperature_profile_for_full_bed(self.design_case, temperature_k)
            validate_profile_temperature_range(profile)

    def test_target_profiles_stay_in_champon_temperature_range(self) -> None:
        for temperature_k in (623.0, 648.0, 673.0):
            result = size_for_target_conversion(
                design_case=self.design_case,
                config=ReactorConfig(
                    temperature_k=temperature_k,
                    pressure_bar=self.design_case.pressure_bar,
                    integration_steps=self.design_case.integration_steps,
                ),
                target_conversion=self.design_case.sizing.target_conversion,
                max_catalyst_mass_kg=self.design_case.sizing.max_catalyst_mass_kg,
            )
            profile = temperature_profile_for_result(self.design_case, result)
            validate_profile_temperature_range(profile)


if __name__ == "__main__":
    unittest.main()

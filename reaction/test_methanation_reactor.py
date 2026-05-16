from __future__ import annotations

import unittest
from pathlib import Path

from reaction.methanation_reactor import (
    ReactorConfig,
    build_summary,
    load_design_case,
    partial_pressures,
    reaction_rates_kmol_per_kgcat_h,
    size_for_target_conversion,
    simulate_fixed_bed,
    temperature_profile_for_result,
    write_reaction_rate_profile_image,
    write_temperature_profile_image,
)


INPUT_PATH = Path(__file__).parent / "inputs" / "input.json"


class MethanationReactorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.design_case = load_design_case(INPUT_PATH)

    def test_three_reactions_are_loaded(self) -> None:
        self.assertEqual(len(self.design_case.reactions), 3)
        self.assertEqual(
            [reaction.name for reaction in self.design_case.reactions],
            ["CO2 methanation", "reverse water-gas shift", "CO methanation"],
        )

    def test_tube_count_is_loaded(self) -> None:
        self.assertEqual(self.design_case.tube_count, 100)

    def test_partial_pressures_follow_feed_ratio(self) -> None:
        pressures = partial_pressures(
            self.design_case.feed.flows_kmol_per_h,
            total_pressure_bar=10.0,
        )
        self.assertAlmostEqual(pressures["CO2"], 2.0)
        self.assertAlmostEqual(pressures["H2"], 8.0)
        self.assertAlmostEqual(pressures["CO"], 0.0)

    def test_all_reaction_rates_are_available(self) -> None:
        rates = reaction_rates_kmol_per_kgcat_h(
            self.design_case.feed.flows_kmol_per_h,
            ReactorConfig(
                temperature_k=350.0,
                pressure_bar=self.design_case.pressure_bar,
                integration_steps=self.design_case.integration_steps,
            ),
            self.design_case.reactions,
        )
        self.assertEqual(set(rates), {reaction.name for reaction in self.design_case.reactions})

    def test_zero_catalyst_mass_keeps_feed_unchanged(self) -> None:
        result = simulate_fixed_bed(
            design_case=self.design_case,
            config=ReactorConfig(
                temperature_k=350.0,
                pressure_bar=self.design_case.pressure_bar,
                integration_steps=self.design_case.integration_steps,
            ),
            catalyst_mass_kg=0.0,
        )
        self.assertEqual(
            result.outlet_flows_kmol_per_h,
            self.design_case.feed.flows_kmol_per_h,
        )
        self.assertEqual(result.target_conversion, 0.0)

    def test_side_reaction_can_generate_co(self) -> None:
        result = simulate_fixed_bed(
            design_case=self.design_case,
            config=ReactorConfig(
                temperature_k=673.0,
                pressure_bar=self.design_case.pressure_bar,
                integration_steps=self.design_case.integration_steps,
            ),
            catalyst_mass_kg=100.0,
        )
        self.assertGreater(result.outlet_flows_kmol_per_h["CO"], 0.0)

    def test_countercurrent_cooling_warms_the_coolant(self) -> None:
        result = simulate_fixed_bed(
            design_case=self.design_case,
            config=ReactorConfig(
                temperature_k=673.0,
                pressure_bar=self.design_case.pressure_bar,
                integration_steps=self.design_case.integration_steps,
            ),
            catalyst_mass_kg=100.0,
        )
        coolant_inlet = (
            self.design_case.thermal.countercurrent_cooling.coolant_inlet_temperature_k
        )
        self.assertGreater(result.coolant_outlet_temperature_k, coolant_inlet)
        self.assertGreater(result.cooling_duty_kj_per_h, 0.0)

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
        self.assertEqual(summary["basis"]["target_species"], "CO2")
        self.assertEqual(summary["basis"]["tube_count"], 100)
        self.assertEqual(len(summary["results"]), 1)
        self.assertIn("ch4_yield_on_co2_feed", summary["results"][0])
        self.assertIn("co_selectivity_on_converted_co2", summary["results"][0])

    def test_temperature_profile_image_is_written(self) -> None:
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
        output_path = Path("/private/tmp/test_temperature_profile.png")
        write_temperature_profile_image(output_path, profile)
        self.assertTrue(output_path.exists())
        self.assertGreater(output_path.stat().st_size, 0)

    def test_reaction_rate_profile_image_is_written(self) -> None:
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
        output_path = Path("/private/tmp/test_reaction_rate_profile.png")
        write_reaction_rate_profile_image(output_path, profile)
        self.assertTrue(output_path.exists())
        self.assertGreater(output_path.stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()

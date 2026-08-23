import unittest

from PSA_simulation.pressure_drop import (
    ergun_pressure_gradient_pa_per_m,
    integrate_ergun_pressure_profile,
)


PROPERTIES = {
    "temperature_k": 313.15,
    "average_molar_mass_g_per_mol": 13.84,
    "viscosity_pa_s": 1.1e-5,
    "bed_void_fraction": 0.4,
    "particle_diameter_m": 0.001,
}


class ErgunPressureDropTests(unittest.TestCase):
    def test_ergun_gradient_is_zero_at_zero_velocity(self):
        gradient = ergun_pressure_gradient_pa_per_m(
            pressure_pa=500_000.0,
            superficial_velocity_m_per_s=0.0,
            **PROPERTIES,
        )
        self.assertEqual(gradient, 0.0)

    def test_forward_profile_falls_toward_recycle_outlet(self):
        profile = integrate_ergun_pressure_profile(
            reference_pressure_kpa=500.0,
            cell_velocities_m_per_s=[0.1] * 10,
            bed_length_m=1.0,
            flow_direction="forward",
            **PROPERTIES,
        )
        self.assertEqual(profile.pressures_kpa[0], 500.0)
        self.assertLess(profile.pressures_kpa[-1], 500.0)
        self.assertTrue(
            all(
                upstream > downstream
                for upstream, downstream in zip(
                    profile.pressures_kpa, profile.pressures_kpa[1:]
                )
            )
        )
        self.assertAlmostEqual(
            profile.pressure_drop_kpa,
            profile.pressures_kpa[0] - profile.pressures_kpa[-1],
        )

    def test_reverse_profile_rises_from_product_outlet_to_purge_inlet(self):
        profile = integrate_ergun_pressure_profile(
            reference_pressure_kpa=10.0,
            cell_velocities_m_per_s=[0.1] * 10,
            bed_length_m=1.0,
            flow_direction="reverse",
            **PROPERTIES,
        )
        self.assertEqual(profile.pressures_kpa[0], 10.0)
        self.assertGreater(profile.pressures_kpa[-1], 10.0)
        self.assertAlmostEqual(
            profile.pressure_drop_kpa,
            profile.pressures_kpa[-1] - profile.pressures_kpa[0],
        )

    def test_forward_profile_rejects_impossible_pressure_loss(self):
        with self.assertRaisesRegex(
            ValueError, "exceeds the available absolute pressure"
        ):
            integrate_ergun_pressure_profile(
                reference_pressure_kpa=1.0,
                cell_velocities_m_per_s=[10.0],
                bed_length_m=100.0,
                flow_direction="forward",
                **PROPERTIES,
            )


if __name__ == "__main__":
    unittest.main()

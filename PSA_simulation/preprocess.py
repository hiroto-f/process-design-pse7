from __future__ import annotations

import math
from dataclasses import dataclass, field

from .models import SimulationInput


R = 8.31451
PI = 3.14159
NUM = 1
H2 = 0
CH4 = 1


@dataclass
class SetupState:
    component_names: list[str] = field(default_factory=list)
    flows_kmol_per_h: list[float] = field(default_factory=list)
    mol_fractions: list[float] = field(default_factory=list)
    two_fractions: list[float] = field(default_factory=list)
    inlet_concentration_kmol_per_m3: list[float] = field(default_factory=lambda: [0.0, 0.0])
    x: list[float] = field(default_factory=lambda: [0.0, 0.0])
    molar_mass: list[float] = field(default_factory=lambda: [0.0, 0.0])
    ek: list[float] = field(default_factory=lambda: [0.0, 0.0])
    sigma: list[float] = field(default_factory=lambda: [0.0, 0.0])
    mu: list[float] = field(default_factory=lambda: [0.0, 0.0])
    dai: list[list[list[float]]] = field(default_factory=lambda: [[[0.0, 0.0] for _ in range(2)] for _ in range(2)])
    dam: list[list[float]] = field(default_factory=lambda: [[0.0, 0.0] for _ in range(2)])
    dkai: list[list[float]] = field(default_factory=lambda: [[0.0, 0.0] for _ in range(2)])
    dkaa: list[list[float]] = field(default_factory=lambda: [[0.0, 0.0] for _ in range(2)])
    dea: list[list[float]] = field(default_factory=lambda: [[0.0, 0.0] for _ in range(2)])
    kfav: list[list[float]] = field(default_factory=lambda: [[0.0, 0.0] for _ in range(2)])
    dp: float = 0.0
    eps: float = 0.0
    epsa: float = 0.0
    epsi: float = 0.0
    ra: float = 0.0
    ri: float = 0.0
    av: float = 0.0
    rho_ads: float = 0.0
    mav: float = 0.0
    mumix: float = 0.0
    tt: float = 0.0
    phigh: float = 0.0
    plow: float = 0.0
    zt_dto: float = 0.0
    uhigh: float = 0.0
    ulow: float = 0.0
    dto: float = 0.0
    zt: float = 0.0
    qt: float = 0.0
    vt: float = 0.0
    volume_flow_m3_per_h: float = 0.0
    feed_pressure_kpa: float = 0.0
    reflux: float = 0.0
    purge_fraction: float | None = None
    adsorption_breakthrough_threshold: float = 0.0
    desorption_residual_loading_threshold: float = 0.0


class Preprocessor:
    def __init__(self, inputs: SimulationInput):
        self.inputs = inputs
        self.state = SetupState()

    def run(self) -> SetupState:
        self.load_feed()
        self.adsorption_data_load()
        self.tower_data_load()
        self.mix_viscosity()
        self.diffusion_coef()
        self.mass_transfer()
        return self.state

    def load_feed(self) -> None:
        feed = self.inputs.feed
        tower = self.inputs.tower
        components = list(feed.components_kmol_per_h)
        flows = [component.flow_kmol_per_h for component in components]
        total_flow = sum(flows)
        two_component_flow = flows[H2] + flows[CH4]
        if two_component_flow <= 0:
            raise ValueError("feed.components_kmol_per_h must include positive H2/CH4 inlet flow values.")

        mol_fractions = [value / total_flow if total_flow else 0.0 for value in flows]
        two_fractions = [
            flows[i] / two_component_flow if i <= NUM else 0.0 for i in range(len(flows))
        ]

        st = self.state
        st.component_names = [component.name for component in components]
        st.flows_kmol_per_h = flows
        st.mol_fractions = mol_fractions
        st.two_fractions = two_fractions
        st.x = two_fractions[:2]
        st.qt = two_component_flow / 3.6
        st.tt = feed.temperature_k if feed.temperature_k is not None else tower.adsorption_temperature_c + 273.15
        st.feed_pressure_kpa = feed.pressure_kpa if feed.pressure_kpa is not None else tower.adsorption_pressure_kpa
        st.volume_flow_m3_per_h = total_flow * R * st.tt / st.feed_pressure_kpa
        st.vt = st.volume_flow_m3_per_h / 3600.0

    def adsorption_data_load(self) -> None:
        ads = self.inputs.adsorbent
        st = self.state

        st.dp = ads.particle_diameter_m
        st.eps = ads.bed_void_fraction
        st.epsa = ads.macro_pore_void_fraction
        st.epsi = ads.micro_pore_void_fraction
        st.ra = ads.macro_pore_radius_m
        st.ri = ads.micro_pore_radius_m
        st.rho_ads = ads.bulk_density_kg_per_m3
        st.av = 6.0 * (1.0 - st.eps) / st.dp

        st.mav = 0.0
        for i, component in enumerate(self.inputs.components):
            st.molar_mass[i] = component.molar_mass_g_per_mol
            st.ek[i] = component.lennard_jones_epsilon_over_k_k
            st.sigma[i] = component.lennard_jones_sigma_angstrom
            st.mav += st.x[i] * st.molar_mass[i]

    def tower_data_load(self) -> None:
        tower = self.inputs.tower
        st = self.state
        st.phigh = tower.adsorption_pressure_kpa
        st.plow = tower.desorption_pressure_kpa
        st.zt_dto = tower.height_to_diameter_ratio
        st.uhigh = tower.adsorption_velocity_m_per_s
        st.adsorption_breakthrough_threshold = tower.adsorption_breakthrough_threshold
        st.desorption_residual_loading_threshold = tower.desorption_residual_loading_threshold
        st.purge_fraction = tower.purge_fraction
        if tower.purge_fraction is not None:
            st.ulow = st.uhigh * st.phigh / st.plow * tower.purge_fraction
        elif tower.desorption_velocity_m_per_s is not None:
            st.ulow = tower.desorption_velocity_m_per_s
        else:
            raise ValueError("tower must define purge_fraction or desorption_velocity_m_per_s.")
        st.dto = math.sqrt(4.0 * st.vt / st.uhigh / PI)
        st.zt = st.zt_dto * st.dto
        st.reflux = st.ulow * st.phigh / st.uhigh / st.plow

    def mix_viscosity(self) -> None:
        st = self.state
        for i in range(2):
            tn = st.tt / st.ek[i]
            omega = 1.16145 / (tn**0.14874) + 0.52487 / math.exp(0.7732 * tn) + 2.16178 / math.exp(2.43787 * tn)
            st.mu[i] = 0.0000026693 * math.sqrt(st.molar_mass[i] * st.tt) / st.sigma[i] / st.sigma[i] / omega

        psi = [[0.0, 0.0], [0.0, 0.0]]
        for i in range(2):
            for j in range(2):
                psi[i][j] = (
                    1.0
                    / math.sqrt(8.0)
                    / math.sqrt(1.0 + st.molar_mass[i] / st.molar_mass[j])
                    * (1.0 + math.sqrt(st.mu[i] / st.mu[j]) * (st.molar_mass[j] / st.molar_mass[i]) ** 0.25) ** 2
                )

        st.mumix = 0.0
        for i in range(2):
            denom = sum(st.x[j] * psi[i][j] for j in range(2))
            st.mumix += st.x[i] * st.mu[i] / denom

    def diffusion_coef(self) -> None:
        st = self.state
        for pressure_index, pressure in enumerate([st.phigh, st.plow]):
            for i in range(2):
                for j in range(2):
                    sigma_d = (st.sigma[i] + st.sigma[j]) / 2.0
                    ek_d = math.sqrt(st.ek[i] * st.ek[j])
                    tn = st.tt / ek_d
                    omega = (
                        1.06036 / (tn**0.1561)
                        + 0.193 / math.exp(0.47635 * tn)
                        + 1.03587 / math.exp(1.52996 * tn)
                        + 1.76474 / math.exp(3.89411 * tn)
                    )
                    st.dai[i][j][pressure_index] = (
                        0.0018583
                        * math.sqrt(st.tt * st.tt * st.tt * (1.0 / st.molar_mass[i] + 1.0 / st.molar_mass[j]))
                        / (pressure * 0.00986923 * sigma_d * sigma_d * omega)
                        / 10000.0
                    )
                denom = sum(st.x[j] / st.dai[i][j][pressure_index] for j in range(2) if i != j)
                st.dam[i][pressure_index] = 1.0 / denom
                st.dkaa[i][pressure_index] = 3.067 * st.ra * math.sqrt(st.tt / (st.molar_mass[i] / 1000.0))
                st.dkai[i][pressure_index] = 3.067 * st.ri * math.sqrt(st.tt / (st.molar_mass[i] / 1000.0))
                st.dea[i][pressure_index] = (
                    st.epsi
                    * st.epsi
                    * (1.0 + 3.0 * st.epsa)
                    / (1.0 - st.epsa)
                    / (1.0 / st.dkai[i][pressure_index] + 1.0 / st.dam[i][pressure_index])
                    + st.epsa
                    * st.epsa
                    / (1.0 / st.dkaa[i][pressure_index] + 1.0 / st.dam[i][pressure_index])
                )

    def mass_transfer(self) -> None:
        st = self.state
        for pressure_index, (pressure, velocity) in enumerate(
            [(st.phigh, st.uhigh), (st.plow, st.ulow)]
        ):
            rho = pressure * 1000.0 / R / st.tt * st.mav * 0.001
            for i in range(2):
                kf = (
                    1.15
                    * velocity
                    / st.eps
                    * ((st.mumix / rho / st.dam[i][pressure_index]) ** (-2.0 / 3.0))
                    * ((velocity * st.dp * rho / st.mumix / st.eps) ** (-0.5))
                )
                mka = 60.0 * st.dea[i][pressure_index] * (1.0 - st.eps) / st.dp / st.dp
                st.kfav[i][pressure_index] = 1.0 / (1.0 / (kf * st.av) + 1.0 / mka)

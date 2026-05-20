from __future__ import annotations

from ..models import SimulationInput
from ..preprocess import SetupState
from .standard import PI, R, ProfileSnapshot, SimulationState


class FastPsaSimulator:
    """Coarse PSA simulator for screening cases before full simulation."""

    def __init__(
        self,
        inputs: SimulationInput,
        setup: SetupState,
        max_steps: int | None = None,
        grid_size: int = 50,
        adsorption_dt: float = 0.00002,
        desorption_dt: float = 0.000005,
        cycles: int = 1,
        save_profiles: bool = False,
    ):
        if grid_size < 5 or grid_size > 100:
            raise ValueError("grid_size must be between 5 and 100.")
        if cycles < 1:
            raise ValueError("cycles must be at least 1.")
        self.inputs = inputs
        self.setup = setup
        self.max_steps = max_steps
        self.grid_size = grid_size
        self.adsorption_dt = adsorption_dt
        self.desorption_dt = desorption_dt
        self.cycles = cycles
        self.save_profiles = save_profiles
        self.state = SimulationState()

    def run(self) -> SimulationState:
        self._load_langmuir_and_feed()
        for cycle_index in range(self.cycles):
            print(f"fast adsorption {cycle_index + 1} 開始")
            self._adsorption(
                "adsorption_1" if cycle_index == 0 else "adsorption_2",
                initialize_empty=(cycle_index == 0),
            )
            print(f"fast desorption {cycle_index + 1} 開始")
            self._desorption()
        return self.state

    def _common_values(self, adsorption: bool):
        st = self.setup
        pt = (st.phigh if adsorption else st.plow) * 1000.0
        u0 = st.uhigh if adsorption else st.ulow
        area = st.dto * st.dto * PI / 4.0
        return st.eps, pt, st.tt, u0, st.zt, st.rho_ads, area

    def _load_langmuir_and_feed(self) -> None:
        for i, component in enumerate(self.inputs.components):
            self.state.qmax[i] = component.langmuir_qmax_mol_per_g
            self.state.b[i] = component.langmuir_b_per_kpa / 1000.0

        volume = self.setup.volume_flow_m3_per_h / 3600.0
        for i in range(2):
            component_flow = self.setup.flows_kmol_per_h[i] / 3600.0
            self.state.c0[i] = component_flow / volume
            self.setup.inlet_concentration_kmol_per_m3[i] = self.state.c0[i]

    def _ceq(self, component: int, qtz: list[float], tt: float) -> float:
        denominator = 1.0 - qtz[0] - qtz[1]
        return 0.001 / (R * tt * self.state.b[component] * self.state.c0[component]) * qtz[component] / denominator

    def _record_profile(
        self,
        profile_name: str,
        time_value: float,
        u0: float,
        u: list[float],
        lt: float,
        dz: float,
        ct_values,
        qt_values,
    ) -> None:
        if not self.save_profiles:
            return
        rows = []
        for k in range(1, self.grid_size + 1):
            rows.append(
                (
                    k * lt * dz,
                    self.state.c0[0] * ct_values[0][k],
                    self.state.c0[1] * ct_values[1][k],
                    self.state.qmax[0] * qt_values[0][k],
                    self.state.qmax[1] * qt_values[1][k],
                    u0 * u[k],
                )
            )
        self.state.profiles[profile_name].append(ProfileSnapshot(time_value, rows))

    def _adsorption(self, profile_name: str, initialize_empty: bool) -> None:
        st = self.state
        st.profiles[profile_name] = []
        eps, pt, tt, u0, lt, rho_ads, area = self._common_values(adsorption=True)
        m = self.grid_size
        dz = 1.0 / m
        dt = self.adsorption_dt
        kfav = [self.setup.kfav[0][0], self.setup.kfav[1][0]]
        cin = [1.0, 1.0]
        qin = [0.0, 0.0]
        f_coef = -dt / eps / dz
        w = -(R * 1000.0) * tt * lt * dz / pt / u0
        g = [kfav[i] * dt * lt / eps / u0 for i in range(2)]
        h = [kfav[i] * dt * lt * st.c0[i] / rho_ads / u0 / st.qmax[i] for i in range(2)]
        u = [0.0] * (m + 2)
        u[0] = 1.0

        for i in range(2):
            st.ct[i][0] = cin[i]
            st.qt[i][0] = qin[i]
        if initialize_empty:
            for k in range(1, m + 1):
                for i in range(2):
                    st.ct[i][k] = 0.0
                    st.qt[i][k] = 0.0
        st.flow_out = [0.0, 0.0]
        self._record_profile(profile_name, 0.0, u0, u, lt, dz, st.ct, st.qt)

        count = 1
        ct_1 = [[0.0] * (m + 2), [0.0] * (m + 2)]
        qt_1 = [[0.0] * (m + 2), [0.0] * (m + 2)]
        ceq = [[0.0] * (m + 2), [0.0] * (m + 2)]

        while True:
            if self.max_steps is not None and count > self.max_steps:
                raise RuntimeError(f"{profile_name}: max_steps={self.max_steps} に到達しました。")
            u[0] = 1.0
            for k in range(1, m + 1):
                qtz = [st.qt[0][k], st.qt[1][k]]
                for i in range(2):
                    st.ct[i][0] = cin[i]
                ceq[0][k] = self._ceq(0, qtz, tt)
                ceq[1][k] = self._ceq(1, qtz, tt)
                u[k] = w * (
                    kfav[0] * st.c0[0] * (st.ct[0][k] - ceq[0][k])
                    + kfav[1] * st.c0[1] * (st.ct[1][k] - ceq[1][k])
                ) + u[k - 1]
                for i in range(2):
                    ct_1[i][k] = (
                        f_coef * st.ct[i][k] * (u[k] - u[k - 1])
                        + f_coef * u[k] * (st.ct[i][k] - st.ct[i][k - 1])
                        - g[i] * (st.ct[i][k] - ceq[i][k])
                        + st.ct[i][k]
                    )
                    qt_1[i][k] = h[i] * (st.ct[i][k] - ceq[i][k]) + qtz[i]
                    if qt_1[i][k] < 0.0:
                        qt_1[i][k] = 0.0
                for i in range(2):
                    st.ct[i][k] = ct_1[i][k]
                    st.qt[i][k] = qt_1[i][k]

            count += 1
            for i in range(2):
                st.flow_out[i] += st.c0[i] * lt * dt * ct_1[i][m] * u[m] * area
            if ct_1[1][m] > self.setup.adsorption_breakthrough_threshold:
                break

        st.end_time[0] = (count - 1) * lt / u0 * dt
        self._record_profile(profile_name, st.end_time[0], u0, u, lt, dz, ct_1, qt_1)

    def _desorption(self) -> None:
        profile_name = "desorption"
        st = self.state
        st.profiles[profile_name] = []
        eps, pt, tt, u0, lt, rho_ads, area = self._common_values(adsorption=False)
        m = self.grid_size
        dz = 1.0 / m
        dt = self.desorption_dt
        kfav = [self.setup.kfav[0][1], self.setup.kfav[1][1]]
        flow_sum = st.flow_out[0] + st.flow_out[1]
        inlet_factor = pt / R / tt / flow_sum / 1000.0
        cin = [st.flow_out[i] * inlet_factor / st.c0[i] for i in range(2)]
        qin = [0.0, 0.0]
        st.regeneration_inlet_concentration = [st.c0[i] * cin[i] for i in range(2)]

        f_coef = -dt / eps / dz
        g = [kfav[i] * dt * lt / eps / u0 for i in range(2)]
        h = [kfav[i] * dt * lt * st.c0[i] / rho_ads / u0 / st.qmax[i] for i in range(2)]
        u = [0.0] * (m + 2)
        for i in range(2):
            st.ct[i][m + 1] = cin[i]
            st.qt[i][m + 1] = qin[i]

        st.purge_out = [0.0, 0.0]
        self._record_profile(profile_name, 0.0, u0, u, lt, dz, st.ct, st.qt)
        count = 1
        ct_1 = [[0.0] * (m + 2), [0.0] * (m + 2)]
        qt_1 = [[0.0] * (m + 2), [0.0] * (m + 2)]
        ceq = [[0.0] * (m + 2), [0.0] * (m + 2)]

        while True:
            if self.max_steps is not None and count > self.max_steps:
                raise RuntimeError(f"{profile_name}: max_steps={self.max_steps} に到達しました。")
            u[m + 1] = 1.0
            for k in range(1, m + 1):
                kk = m + 1 - k
                qtz = [st.qt[0][kk], st.qt[1][kk]]
                ceq[0][kk] = self._ceq(0, qtz, tt)
                ceq[1][kk] = self._ceq(1, qtz, tt)
                u[kk] = u[kk + 1]
                for i in range(2):
                    ct_1[i][kk] = (
                        f_coef * u[kk] * (st.ct[i][kk] - st.ct[i][kk + 1])
                        - g[i] * (st.ct[i][kk] - ceq[i][kk])
                        + st.ct[i][kk]
                    )
                    qt_1[i][kk] = h[i] * (st.ct[i][kk] - ceq[i][kk]) + qtz[i]
                    if qt_1[i][kk] < 0.0:
                        qt_1[i][kk] = 0.0
                for i in range(2):
                    st.ct[i][kk] = ct_1[i][kk]
                    st.qt[i][kk] = qt_1[i][kk]

            count += 1
            for i in range(2):
                st.purge_out[i] += st.c0[i] * lt * dt * ct_1[i][1] * u[1] * area
            if qt_1[1][1] < self.setup.desorption_residual_loading_threshold:
                break

        st.end_time[1] = (count - 1) * lt / u0 * dt
        self._record_profile(profile_name, st.end_time[1], u0, u, lt, dz, ct_1, qt_1)
        st.product_out = [
            st.flow_out[i] - st.c0[i] * cin[i] * u0 * area * st.end_time[1]
            for i in range(2)
        ]

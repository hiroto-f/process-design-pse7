import numpy as np
from scipy.integrate import solve_ivp


class IsothermalPFR:

    def __init__(self, kinetics, T, P):

        self.kinetics = kinetics
        self.T = T
        self.P = P

    def ode(self, W, F):

        r1, r2, r3 = self.kinetics.rates(
            self.T,
            self.P,
            F
        )

        dF = np.zeros(5)

        # CO2
        dF[0] = r2 - r3

        # H2
        dF[1] = 3*r1 + r2 + 4*r3

        # CH4
        dF[2] = -r1 - r3

        # H2O
        dF[3] = -r1 - r2 - 2*r3

        # CO
        dF[4] = -r1 + r2

        return dF

    def solve(self, F0, Wmax):

        sol = solve_ivp(
            self.ode,
            (0, Wmax),
            F0,
            method="BDF",
            atol=1e-10,
            rtol=1e-8
        )

        return sol
"""Sensitivity-based MPC controller for Volt-VAR control.

Implements the same ``predict(obs, deterministic)`` interface as SB3 policies
so it can be dropped into the existing ``vvc-eval`` CLI without modification.

Algorithm
---------
At each call to :meth:`MPCController.predict`:

1. Numerically estimate the voltage sensitivity matrix S (shape n_bus x n_pv)
   by perturbing each PV's reactive power by +/-delta and measuring the
   resulting bus voltage changes via OpenDSS.
2. Restore all PV kvar to 0 and re-solve so the environment's next
   ``step()`` call starts from a clean, unperturbed state.
3. Solve the small QP::

       minimise   sum(q_j^2)
       subject to v_min <= V_nom + S @ q <= v_max
                  -1 <= q_j <= 1      (normalised units)

   using ``scipy.optimize.minimize`` with method="SLSQP".
4. Return the clipped solution (or zeros on failure) as a float32 array.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize, LinearConstraint, Bounds
from opendssdirect import dss

from volt_var_env.env import _DIST_BUSES, _PV_NAMES, _PV_KVA

_N_BUS = len(_DIST_BUSES)
_N_PV  = len(_PV_NAMES)

# Pre-build a lower-case lookup table once at import time so _get_bus_voltages
# does not have to call str.lower() inside a hot loop.
_BUS_ORDER = [b.lower() for b in _DIST_BUSES]


class MPCController:
    """One-step sensitivity MPC with a voltage-feasibility QP.

    Parameters
    ----------
    v_min:
        Lower voltage limit in pu (default 0.95).
    v_max:
        Upper voltage limit in pu (default 1.05).
    delta:
        Reactive-power perturbation used for finite-difference sensitivity
        estimation, expressed as a fraction of rated kVA (default 0.05,
        i.e. 5 % of rating).
    """

    def __init__(
        self,
        v_min: float = 0.95,
        v_max: float = 1.05,
        delta: float = 0.05,
    ) -> None:
        self.v_min = float(v_min)
        self.v_max = float(v_max)
        self.delta = float(delta)

    # ── Public SB3-compatible interface ──────────────────────────────────────

    def predict(
        self,
        obs: np.ndarray,
        deterministic: bool = True,
    ) -> tuple[np.ndarray, None]:
        """Compute a reactive-power setpoint via sensitivity-based MPC.

        Parameters
        ----------
        obs:
            Observation vector from :class:`~volt_var_env.env.VoltVAREnv`.
            Shape ``(17,)`` or ``(batch, 17)``.  Only the first 12 elements
            (per-bus voltages) are used.
        deterministic:
            Ignored; present only for API compatibility with SB3 policies.

        Returns
        -------
        action : np.ndarray, shape ``(4,)`` or ``(batch, 4)``
            Normalised reactive-power setpoints in ``[-1, 1]``.
        states : None
            Always ``None`` (no recurrent state).
        """
        single = obs.ndim == 1
        if single:
            obs = obs[np.newaxis]  # (1, obs_dim)

        results = []
        for row in obs:
            results.append(self._predict_single(row))

        actions = np.stack(results, axis=0).astype(np.float32)
        return (actions[0] if single else actions), None

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _predict_single(self, obs: np.ndarray) -> np.ndarray:
        """Run MPC for one observation vector."""
        # Current bus voltages from obs (indices 0..11 map to _DIST_BUSES).
        V_nom = obs[:_N_BUS].astype(np.float64)

        # Build sensitivity matrix and restore a clean simulation state.
        S = self._sensitivity()

        # Solve the QP.
        q_opt = self._solve(S, V_nom)
        return q_opt.astype(np.float32)

    def _get_bus_voltages(self) -> np.ndarray:
        """Return bus voltage magnitudes in pu, indexed by ``_DIST_BUSES``.

        Reads the current OpenDSS solution state.  Returns 1.0 for any bus
        not found in the circuit (should not happen on a healthy feeder).
        """
        names = [n.lower() for n in dss.Circuit.AllBusNames()]
        mags  = list(dss.Circuit.AllBusMagPu())
        bus_map: dict[str, float] = dict(zip(names, mags))
        return np.array([bus_map.get(b, 1.0) for b in _BUS_ORDER], dtype=np.float64)

    def _sensitivity(self) -> np.ndarray:
        """Numerically compute the voltage sensitivity matrix dV/dQ.

        Shape: ``(n_bus, n_pv)`` where entry ``[i, j]`` is the partial
        derivative of bus ``i`` voltage (pu) with respect to PV ``j``
        reactive-power setpoint (in normalised ``[-1, 1]`` units, i.e.
        per unit of rated kVA).

        Uses a central finite difference: perturb PV j by +delta, record
        voltages V+; perturb by -delta, record V-; then dV/dQ_j = (V+ - V-) /
        (2*delta).  All other PVs remain at 0 kvar during each perturbation.

        After all perturbations the method resets every PV to 0 kvar and
        re-solves so the caller's subsequent ``env.step()`` starts clean.
        """
        S = np.zeros((_N_BUS, _N_PV), dtype=np.float64)

        for j, (name, kva) in enumerate(zip(_PV_NAMES, _PV_KVA)):
            delta_kvar = self.delta * kva

            # Positive perturbation
            dss.Text.Command(f"Edit PVSystem.{name} kvar={delta_kvar:.2f}")
            dss.Solution.Solve()
            V_pos = self._get_bus_voltages()

            # Negative perturbation
            dss.Text.Command(f"Edit PVSystem.{name} kvar={-delta_kvar:.2f}")
            dss.Solution.Solve()
            V_neg = self._get_bus_voltages()

            # Restore this PV to zero before moving to the next column
            dss.Text.Command(f"Edit PVSystem.{name} kvar=0.00")

            S[:, j] = (V_pos - V_neg) / (2.0 * self.delta)

        # Final clean solve with all PVs at 0 kvar so env.step() can overwrite Q.
        dss.Solution.Solve()

        return S

    def _solve(self, S: np.ndarray, V_nom: np.ndarray) -> np.ndarray:
        """Solve the reactive-power optimisation QP.

        Minimise   f(q) = sum(q_j^2)
        subject to v_min <= V_nom + S @ q <= v_max
                   -1 <= q_j <= 1

        Uses ``scipy.optimize.minimize`` with SLSQP.  Falls back to an
        all-zeros action if the optimiser fails to converge.

        Parameters
        ----------
        S : ndarray, shape (n_bus, n_pv)
            Voltage sensitivity matrix (pu voltage per normalised-Q unit).
        V_nom : ndarray, shape (n_bus,)
            Nominal bus voltages before any reactive-power injection (pu).

        Returns
        -------
        q : ndarray, shape (n_pv,), values in [-1, 1]
            Optimal normalised reactive-power setpoints.
        """
        q0 = np.zeros(_N_PV, dtype=np.float64)

        def objective(q: np.ndarray) -> float:
            return float(np.dot(q, q))

        def gradient(q: np.ndarray) -> np.ndarray:
            return 2.0 * q

        # Linear constraint: v_min - V_nom <= S @ q <= v_max - V_nom
        lb = self.v_min - V_nom   # shape (n_bus,)
        ub = self.v_max - V_nom   # shape (n_bus,)
        voltage_constraint = LinearConstraint(S, lb, ub)

        # Box bounds: each q_j in [-1, 1]
        bounds = Bounds(lb=-np.ones(_N_PV), ub=np.ones(_N_PV))

        result = minimize(
            fun=objective,
            x0=q0,
            jac=gradient,
            method="SLSQP",
            constraints=[voltage_constraint],
            bounds=bounds,
            options={"ftol": 1e-8, "maxiter": 200, "disp": False},
        )

        if result.success or result.status in (0, 1, 9):
            # status 9 = iteration limit reached but still a usable solution
            q_opt = np.clip(result.x, -1.0, 1.0)
        else:
            # Fall back to zero reactive power on failure
            q_opt = np.zeros(_N_PV, dtype=np.float64)

        return q_opt

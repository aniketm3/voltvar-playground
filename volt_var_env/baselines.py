"""Baseline controllers for Volt-VAR control."""

from __future__ import annotations

import numpy as np

# Observation indices of the PV bus voltages (must match _DIST_BUSES order in env.py)
# _DIST_BUSES = ["632","633","634","645","646","671","684","611","652","680","692","675"]
#  PV675 → bus 675 → idx 11
#  PV680 → bus 680 → idx 9
#  PV611 → bus 611 → idx 7
#  PV652 → bus 652 → idx 8
_PV_BUS_OBS_IDX = [11, 9, 7, 8]


class DroopController:
    """IEEE 1547-2018 style Volt-VAR droop curve controller.

    Maps each PV inverter's local bus voltage to a normalised reactive-power
    setpoint in [-1, 1] using a four-point piecewise-linear droop:

        v < v1          →  q = +1  (max VAR injection, raise voltage)
        v1 ≤ v < v2     →  linear ramp  +1 → 0
        v2 ≤ v ≤ v3     →  q = 0  (deadband)
        v3 < v ≤ v4     →  linear ramp  0 → -1
        v > v4          →  q = -1  (max VAR absorption, lower voltage)

    The default breakpoints are tuned for the IEEE 13-bus feeder with a
    source voltage of 1.05 pu.
    """

    def __init__(
        self,
        v1: float = 0.95,
        v2: float = 0.98,
        v3: float = 1.02,
        v4: float = 1.05,
    ):
        assert v1 < v2 < v3 < v4, "Breakpoints must be strictly increasing"
        self.v1, self.v2, self.v3, self.v4 = v1, v2, v3, v4

    def predict(
        self,
        obs: np.ndarray,
        deterministic: bool = True,
    ) -> tuple[np.ndarray, None]:
        """SB3-compatible interface: returns (actions, states)."""
        single = obs.ndim == 1
        if single:
            obs = obs[np.newaxis]

        actions = np.zeros((obs.shape[0], len(_PV_BUS_OBS_IDX)), dtype=np.float32)
        for i, v_idx in enumerate(_PV_BUS_OBS_IDX):
            actions[:, i] = self._droop(obs[:, v_idx])

        return (actions[0] if single else actions), None

    def _droop(self, v: np.ndarray) -> np.ndarray:
        v = np.asarray(v, dtype=np.float64)
        q = np.zeros_like(v)
        q[v < self.v1] = 1.0
        mask = (v >= self.v1) & (v < self.v2)
        q[mask] = (self.v2 - v[mask]) / (self.v2 - self.v1)
        mask = (v > self.v3) & (v <= self.v4)
        q[mask] = -(v[mask] - self.v3) / (self.v4 - self.v3)
        q[v > self.v4] = -1.0
        return q.astype(np.float32)


class ZeroController:
    """Always outputs zero reactive power (no VVC)."""

    def predict(self, obs: np.ndarray, deterministic: bool = True):
        single = obs.ndim == 1
        n_pv = len(_PV_BUS_OBS_IDX)
        if single:
            return np.zeros(n_pv, dtype=np.float32), None
        return np.zeros((obs.shape[0], n_pv), dtype=np.float32), None

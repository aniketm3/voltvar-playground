"""Baseline controllers for Volt-VAR control."""

from __future__ import annotations

import numpy as np


class DroopController:
    """IEEE 1547-2018 style Volt-VAR droop curve controller.

    Each PV inverter reads its local bus voltage from the observation vector
    (at pv_bus_obs_idx) and outputs a normalised kVAR setpoint in [-1, 1].
    """

    def __init__(
        self,
        pv_bus_obs_idx: list[int],
        v1: float = 0.95,
        v2: float = 0.98,
        v3: float = 1.02,
        v4: float = 1.05,
    ):
        assert v1 < v2 < v3 < v4
        self.pv_bus_obs_idx = pv_bus_obs_idx
        self.v1, self.v2, self.v3, self.v4 = v1, v2, v3, v4

    def predict(self, obs: np.ndarray, deterministic: bool = True):
        single = obs.ndim == 1
        if single:
            obs = obs[np.newaxis]

        actions = np.zeros((obs.shape[0], len(self.pv_bus_obs_idx)), dtype=np.float32)
        for i, v_idx in enumerate(self.pv_bus_obs_idx):
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

    def __init__(self, n_pv: int):
        self.n_pv = n_pv

    def predict(self, obs: np.ndarray, deterministic: bool = True):
        single = obs.ndim == 1
        if single:
            return np.zeros(self.n_pv, dtype=np.float32), None
        return np.zeros((obs.shape[0], self.n_pv), dtype=np.float32), None

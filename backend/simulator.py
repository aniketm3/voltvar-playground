"""Simulation engine: wraps VoltVAREnv with per-inverter solar control.

OpenDSS is a process-level singleton, so all simulation calls are serialized
behind a threading.Lock. FastAPI dispatches them via run_in_executor.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Literal

import numpy as np
from opendssdirect import dss
from stable_baselines3 import SAC

from volt_var_env import VoltVAREnv, DomainRandomConfig
from volt_var_env.baselines import DroopController, ZeroController
from volt_var_env.env import _PV_NAMES, _PV_KVA, _BASE_LOADS
from volt_var_env.profiles import solar_profile, load_profile

CIRCUIT_PATH = Path(__file__).parents[2] / "volt-VAR-control" / "circuits" / "ieee13.dss"
MODELS_ROOT  = Path(__file__).parents[2] / "volt-VAR-control" / "results"

_TOTAL_BASE_LOAD_KW = sum(kw for kw, _ in _BASE_LOADS.values())

PolicyName = Literal["sac_both", "sac_none", "droop", "zero"]

_DIST_BUSES = [
    "632", "633", "634", "645", "646",
    "671", "684", "611", "652", "680", "692", "675",
]


class SimulationEngine:
    """Loads all policies once at startup; exposes thread-safe simulate() methods."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._env = VoltVAREnv(CIRCUIT_PATH, dr_config=DomainRandomConfig())

        # Deterministic (no-noise) base profiles — per-inverter overrides are
        # applied on top of these at request time.
        rng = np.random.default_rng(0)
        self._base_solar = solar_profile(96, scale=1.0, noise_std=0.0, rng=rng)
        self._base_load  = load_profile(96,  scale=1.0, noise_std=0.0, rng=rng)

        self._policies: dict[PolicyName, object] = {
            "droop": DroopController(),
            "zero":  ZeroController(),
        }
        self._load_sac("sac_both", "sac_both/seed_0/sac_both/best_model.zip")
        self._load_sac("sac_none", "sac_none/seed_0/sac_none/best_model.zip")

    def _load_sac(self, name: PolicyName, rel_path: str) -> None:
        path = MODELS_ROOT / rel_path
        if path.exists():
            self._policies[name] = SAC.load(str(path), env=self._env)
        else:
            print(f"[warn] model not found: {path}; falling back to droop for {name}")
            self._policies[name] = DroopController()

    # ── Public API ────────────────────────────────────────────────────────────

    def simulate_step(
        self,
        policy: PolicyName,
        timestep: int,
        solar_scales: list[float],
        cloud_covers: list[float],
        load_scale: float,
    ) -> dict:
        with self._lock:
            return self._run_step(policy, timestep, solar_scales, cloud_covers, load_scale)

    def simulate_episode(
        self,
        policy: PolicyName,
        solar_scales: list[float],
        cloud_covers: list[float],
        load_scale: float,
    ) -> dict:
        with self._lock:
            steps = [
                self._run_step(policy, t, solar_scales, cloud_covers, load_scale)
                for t in range(self._env.episode_steps)
            ]
            return {"episode": steps}

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run_step(
        self,
        policy: PolicyName,
        timestep: int,
        solar_scales: list[float],
        cloud_covers: list[float],
        load_scale: float,
    ) -> dict:
        env = self._env
        t = int(np.clip(timestep, 0, env.episode_steps - 1))

        # Inject deterministic profiles scaled by load_scale.
        env._solar_profile = self._base_solar.copy()
        env._load_profile  = self._base_load * load_scale
        env._per_load_noise = {n: 0.0 for n in env._per_load_noise}

        # Set up OpenDSS circuit at this timestep.
        env._load_circuit()
        env._t = t
        env._apply_timestep()

        # Per-inverter irradiance override: base curve × solar_scale × (1-cloud_cover).
        base_irr = float(self._base_solar[t])
        for pv_name, s_scale, c_cover in zip(_PV_NAMES, solar_scales, cloud_covers):
            irr = float(np.clip(base_irr * s_scale * (1.0 - c_cover), 0.0, 2.0))
            dss.Text.Command(f"Edit PVSystem.{pv_name} irradiance={irr:.4f}")
        dss.Solution.Solve()

        obs = env._get_obs()
        action, _ = self._policies[policy].predict(obs, deterministic=True)
        action = np.clip(action, -1.0, 1.0).astype(np.float32)

        env._set_pv_kvar(action)
        dss.Solution.Solve()

        info = env._get_info()
        bus_v_map = env._bus_voltage_map()

        voltages = {b: round(float(bus_v_map.get(b, 1.0)), 5) for b in _DIST_BUSES}
        pv_kvar  = {
            name: round(float(act) * kva, 2)
            for name, act, kva in zip(_PV_NAMES, action, _PV_KVA)
        }
        pv_active_kw: dict[str, float] = {}
        for pv_name, kva in zip(_PV_NAMES, _PV_KVA):
            dss.PVsystems.Name(pv_name)
            pv_active_kw[pv_name] = round(abs(dss.PVsystems.kW()), 2)

        volt_penalty = sum(
            max(0.0, v - env.v_max) ** 2 + max(0.0, env.v_min - v) ** 2
            for v in voltages.values()
        )
        load_kw = _TOTAL_BASE_LOAD_KW * float(self._base_load[t]) * load_scale
        losses_pu = info["losses_kw"] / max(load_kw, 1.0)
        reward = -env.alpha * volt_penalty - env.beta * losses_pu

        return {
            "timestep": t,
            "voltages": voltages,
            "pv_kvar": pv_kvar,
            "pv_active_kw": pv_active_kw,
            "n_violations": info["n_violations"],
            "violation_buses": info["violation_buses"],
            "losses_kw": round(info["losses_kw"], 3),
            "reward": round(reward, 4),
        }

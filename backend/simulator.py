"""Simulation engine: wraps VoltVAREnv with per-inverter solar control.

OpenDSS is a process-level singleton, so all simulation calls are serialized
behind a threading.Lock. FastAPI dispatches them via run_in_executor.
"""

from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Literal

# Add repo root so volt_var_env is importable without an editable install.
sys.path.insert(0, str(Path(__file__).parents[1]))

import numpy as np
from opendssdirect import dss
from stable_baselines3 import SAC

from volt_var_env import VoltVAREnv, DomainRandomConfig
from volt_var_env.baselines import DroopController, ZeroController
from volt_var_env.env import _PV_NAMES, _PV_KVA, _BASE_LOADS
from volt_var_env.profiles import solar_profile, load_profile

CIRCUIT_PATH = Path(__file__).parents[1] / "circuits" / "ieee13.dss"
MODELS_ROOT  = Path(__file__).parents[1] / "models"

_TOTAL_BASE_LOAD_KW = sum(kw for kw, _ in _BASE_LOADS.values())

PolicyName = Literal["sac_both", "sac_none", "droop", "zero"]

DIST_BUSES = [
    "632", "633", "634", "645", "646",
    "671", "684", "611", "652", "680", "692", "675",
]


class SimulationEngine:
    """Loads all policies once at startup; exposes thread-safe simulate() methods."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._env = VoltVAREnv(CIRCUIT_PATH, dr_config=DomainRandomConfig())

        # Deterministic base profiles (no noise) — per-inverter overrides applied on top.
        rng = np.random.default_rng(0)
        self._base_solar = solar_profile(96, scale=1.0, noise_std=0.0, rng=rng)
        self._base_load  = load_profile(96,  scale=1.0, noise_std=0.0, rng=rng)

        self._policies: dict[PolicyName, object] = {
            "droop": DroopController(),
            "zero":  ZeroController(),
        }
        self._load_sac("sac_both", "sac_both/best_model.zip")
        self._load_sac("sac_none", "sac_none/best_model.zip")

    def _load_sac(self, name: PolicyName, rel_path: str) -> None:
        path = MODELS_ROOT / rel_path
        if path.exists():
            self._policies[name] = SAC.load(str(path), env=self._env)
        else:
            print(f"[warn] {path} not found; falling back to droop for {name}")
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
        """Run a full 96-step episode. Loads the circuit once, not per-step."""
        with self._lock:
            env = self._env
            self._configure_profiles(env, load_scale)

            env._load_circuit()
            env._t = 0
            env._apply_timestep()
            self._override_irradiance(0, solar_scales, cloud_covers)
            dss.Solution.Solve()

            steps = []
            for t in range(env.episode_steps):
                obs = env._get_obs()
                action, _ = self._policies[policy].predict(obs, deterministic=True)
                action = np.clip(action, -1.0, 1.0).astype(np.float32)

                env._set_pv_kvar(action)
                dss.Solution.Solve()
                steps.append(self._collect(env, t, action, load_scale))

                env._t = t + 1
                if t + 1 < env.episode_steps:
                    env._apply_timestep()
                    self._override_irradiance(t + 1, solar_scales, cloud_covers)
                    dss.Solution.Solve()

            return {"episode": steps}

    # ── Internal ──────────────────────────────────────────────────────────────

    def _configure_profiles(self, env: VoltVAREnv, load_scale: float) -> None:
        env._solar_profile = self._base_solar.copy()
        env._load_profile  = self._base_load * load_scale
        env._per_load_noise = {n: 0.0 for n in env._per_load_noise}

    def _override_irradiance(
        self,
        t: int,
        solar_scales: list[float],
        cloud_covers: list[float],
    ) -> None:
        base = float(self._base_solar[t])
        for pv, s, c in zip(_PV_NAMES, solar_scales, cloud_covers):
            irr = float(np.clip(base * s * (1.0 - c), 0.0, 2.0))
            dss.Text.Command(f"Edit PVSystem.{pv} irradiance={irr:.4f}")

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

        self._configure_profiles(env, load_scale)
        env._load_circuit()
        env._t = t
        env._apply_timestep()
        self._override_irradiance(t, solar_scales, cloud_covers)
        dss.Solution.Solve()

        obs = env._get_obs()
        action, _ = self._policies[policy].predict(obs, deterministic=True)
        action = np.clip(action, -1.0, 1.0).astype(np.float32)

        env._set_pv_kvar(action)
        dss.Solution.Solve()
        return self._collect(env, t, action, load_scale)

    def _collect(
        self,
        env: VoltVAREnv,
        t: int,
        action: np.ndarray,
        load_scale: float,
    ) -> dict:
        info      = env._get_info()
        bus_v_map = env._bus_voltage_map()

        voltages = {b: round(float(bus_v_map.get(b, 1.0)), 5) for b in DIST_BUSES}
        pv_kvar  = {
            name: round(float(act) * kva, 2)
            for name, act, kva in zip(_PV_NAMES, action, _PV_KVA)
        }
        pv_active_kw: dict[str, float] = {}
        for pv_name, kva in zip(_PV_NAMES, _PV_KVA):
            dss.PVsystems.Name(pv_name)
            pv_active_kw[pv_name] = round(abs(dss.PVsystems.kW()), 2)

        load_kw = _TOTAL_BASE_LOAD_KW * float(self._base_load[t]) * load_scale
        volt_penalty = sum(
            max(0.0, v - env.v_max) ** 2 + max(0.0, env.v_min - v) ** 2
            for v in voltages.values()
        )
        losses_pu = info["losses_kw"] / max(load_kw, 1.0)
        reward = -env.alpha * volt_penalty - env.beta * losses_pu

        return {
            "timestep":       t,
            "voltages":       voltages,
            "pv_kvar":        pv_kvar,
            "pv_active_kw":   pv_active_kw,
            "n_violations":   info["n_violations"],
            "violation_buses": info["violation_buses"],
            "losses_kw":      round(info["losses_kw"], 3),
            "reward":         round(reward, 4),
        }

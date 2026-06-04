"""OpenDSS gymnasium environment for Volt-VAR control."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import gymnasium as gym
from gymnasium import spaces
from opendssdirect import dss

from volt_var_env.grid_config import GridConfig
from volt_var_env.profiles import solar_profile, load_profile


# ── Domain-randomisation configuration ──────────────────────────────────────

@dataclass
class DomainRandomConfig:
    randomize_solar_load: bool = False
    randomize_grid_params: bool = False
    solar_scale_range: tuple[float, float] = (0.5, 1.5)
    load_scale_range:  tuple[float, float] = (0.7, 1.3)
    load_noise_std:    float = 0.05
    line_r_scale_range: tuple[float, float] = (0.8, 1.2)
    line_x_scale_range: tuple[float, float] = (0.8, 1.2)
    cap_scale_range:    tuple[float, float] = (0.5, 1.5)


# ── Environment ──────────────────────────────────────────────────────────────

class VoltVAREnv(gym.Env):
    """Gymnasium environment for Volt-VAR control on a parameterised feeder.

    Observation (n_buses + n_pv + 1):
        v[0:n_buses]            per-bus voltage magnitude in pu
        p[n_buses:n_buses+n_pv] PV active-power output in pu of rated kVA
        t[-1]                   time-of-day normalised to [0, 1]

    Action (n_pv, float32 in [-1, 1]):
        Normalised reactive-power setpoints mapped to [-kVA, +kVA] kVAR.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        config: GridConfig,
        dr_config: Optional[DomainRandomConfig] = None,
        episode_steps: int = 96,
        alpha: float = 10.0,
        beta: float = 1.0,
        v_min: float = 0.95,
        v_max: float = 1.05,
    ):
        super().__init__()
        self.config        = config
        self.dr_config     = dr_config or DomainRandomConfig()
        self.episode_steps = episode_steps
        self.alpha = alpha
        self.beta  = beta
        self.v_min = v_min
        self.v_max = v_max

        obs_dim = config.obs_dim
        n_pv    = config.n_pv

        self.observation_space = spaces.Box(
            low=np.zeros(obs_dim, dtype=np.float32),
            high=np.full(obs_dim, 2.0, dtype=np.float32),
            dtype=np.float32,
        )
        self.action_space = spaces.Box(
            low=-np.ones(n_pv, dtype=np.float32),
            high=np.ones(n_pv, dtype=np.float32),
            dtype=np.float32,
        )

        self._t: int = 0
        self._solar_profile = np.ones(episode_steps, dtype=np.float32)
        self._load_profile  = np.ones(episode_steps, dtype=np.float32)
        self._per_load_noise: dict[str, float] = {n: 0.0 for n in config.base_loads}

        self._load_circuit()

    # ── Gymnasium API ────────────────────────────────────────────────────────

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        rng = self.np_random
        self._t = 0
        self._load_circuit(rng=rng)
        self._generate_profiles(rng=rng)
        self._apply_timestep()
        dss.Solution.Solve()
        return self._get_obs(), {}

    def step(self, action):
        action = np.clip(action, -1.0, 1.0).astype(np.float32)
        self._set_pv_kvar(action)
        dss.Solution.Solve()

        reward = self._compute_reward()
        info   = self._get_info()

        self._t += 1
        truncated  = self._t >= self.episode_steps
        terminated = False

        if not truncated:
            self._apply_timestep()
            dss.Solution.Solve()

        return self._get_obs(), reward, terminated, truncated, info

    # ── Circuit management ───────────────────────────────────────────────────

    def _load_circuit(self, rng=None):
        dss.Text.Command("Clear")
        dss.Text.Command(f"Redirect {self.config.circuit_path}")

        cfg = self.dr_config
        if cfg.randomize_grid_params and rng is not None and self.config.base_linecodes:
            r_scale   = float(rng.uniform(*cfg.line_r_scale_range))
            x_scale   = float(rng.uniform(*cfg.line_x_scale_range))
            cap_scale = float(rng.uniform(*cfg.cap_scale_range))
            self._apply_grid_randomization(r_scale, x_scale, cap_scale)

        dss.Solution.Solve()

    def _apply_grid_randomization(self, r_scale, x_scale, cap_scale):
        for code, data in self.config.base_linecodes.items():
            nph = data["nphases"]
            if nph == 1:
                r = data["R"][0] * r_scale
                x = data["X"][0] * x_scale
                dss.Text.Command(f"Edit Linecode.{code} R1={r:.6f} X1={x:.6f}")
            else:
                r_vals = [v * r_scale for v in data["R"]]
                x_vals = [v * x_scale for v in data["X"]]
                dss.Text.Command(
                    f"Edit Linecode.{code} "
                    f"Rmatrix={_mat_str(r_vals, nph)} "
                    f"Xmatrix={_mat_str(x_vals, nph)}"
                )
        for cap_name, base_kvar in self.config.base_caps.items():
            dss.Text.Command(f"Edit Capacitor.{cap_name} kvar={base_kvar * cap_scale:.2f}")

    # ── Profile management ───────────────────────────────────────────────────

    def _generate_profiles(self, rng=None):
        cfg = self.dr_config
        if cfg.randomize_solar_load and rng is not None:
            s_scale   = float(rng.uniform(*cfg.solar_scale_range))
            l_scale   = float(rng.uniform(*cfg.load_scale_range))
            noise_std = cfg.load_noise_std
        else:
            s_scale = l_scale = 1.0
            noise_std = 0.0

        self._solar_profile = solar_profile(self.episode_steps, scale=s_scale,
                                             noise_std=noise_std, rng=rng)
        self._load_profile  = load_profile(self.episode_steps,  scale=l_scale,
                                            noise_std=noise_std, rng=rng)

        if rng is not None and noise_std > 0:
            self._per_load_noise = {
                n: float(rng.normal(0.0, noise_std)) for n in self.config.base_loads
            }
        else:
            self._per_load_noise = {n: 0.0 for n in self.config.base_loads}

    def _apply_timestep(self):
        irr       = float(self._solar_profile[self._t])
        load_mult = float(self._load_profile[self._t])

        for pv_name in self.config.pv_names:
            dss.Text.Command(f"Edit PVSystem.{pv_name} irradiance={irr:.4f}")

        for load_name, (kw_base, kvar_base) in self.config.base_loads.items():
            mult = max(0.0, load_mult + self._per_load_noise.get(load_name, 0.0))
            dss.Text.Command(
                f"Edit Load.{load_name} kw={kw_base * mult:.2f} kvar={kvar_base * mult:.2f}"
            )

    # ── Action application ───────────────────────────────────────────────────

    def _set_pv_kvar(self, action):
        for pv_name, act, kva in zip(self.config.pv_names, action, self.config.pv_kva):
            dss.Text.Command(f"Edit PVSystem.{pv_name} kvar={float(act) * kva:.2f}")

    # ── Observation and reward ───────────────────────────────────────────────

    def _bus_voltage_map(self) -> dict[str, float]:
        # VMagAngle() returns actual phase-to-neutral voltages in V.
        # kVBase() is unreliable for simple radial circuits (CalcVoltageBases
        # can produce wrong values when there's no transformer).
        # Use GridConfig.voltage_kv as the nominal base for all main-voltage
        # buses; fall back to kVBase() only for buses at a distinctly different
        # level (e.g. transformer secondary like the 13-bus 634 bus at 0.48 kV).
        nominal_v = self.config.voltage_kv * 1000.0 / (3.0 ** 0.5)  # V, line-to-ground
        result = {}
        for name in [n.lower() for n in dss.Circuit.AllBusNames()]:
            dss.Circuit.SetActiveBus(name)
            vmag_angle = dss.Bus.VMagAngle()  # [mag_V, angle_deg, ...]
            if not vmag_angle:
                result[name] = 1.0
                continue
            mags   = vmag_angle[::2]
            avg_v  = float(sum(mags) / len(mags))
            kv_base = dss.Bus.kVBase()
            local_v = kv_base * 1000.0
            # If kVBase indicates a transformer secondary (>15% off from nominal)
            # use it; otherwise use the config nominal as the base.
            if local_v > 0 and abs(local_v - nominal_v) / nominal_v > 0.15:
                base_v = local_v
            else:
                base_v = nominal_v
            result[name] = avg_v / base_v
        return result

    def _get_obs(self):
        bus_v    = self._bus_voltage_map()
        volt_vec = np.array([bus_v.get(b, 1.0) for b in self.config.dist_buses],
                            dtype=np.float32)
        pv_p   = np.array(self._pv_active_power_pu(), dtype=np.float32)
        t_norm = np.array([self._t / self.episode_steps], dtype=np.float32)
        return np.concatenate([volt_vec, pv_p, t_norm])

    def _pv_active_power_pu(self):
        result = []
        for pv_name, kva in zip(self.config.pv_names, self.config.pv_kva):
            dss.PVsystems.Name(pv_name)
            result.append(abs(dss.PVsystems.kW()) / kva)
        return result

    def _compute_reward(self):
        bus_v = self._bus_voltage_map()
        volt_penalty = sum(
            max(0.0, v - self.v_max) ** 2 + max(0.0, self.v_min - v) ** 2
            for v in bus_v.values()
        )
        losses_kw = dss.Circuit.Losses()[0] / 1000.0
        t_idx  = min(max(self._t - 1, 0), self.episode_steps - 1)
        load_kw = self.config.total_base_load_kw * float(self._load_profile[t_idx])
        losses_pu = losses_kw / max(load_kw, 1.0)
        return float(-self.alpha * volt_penalty - self.beta * losses_pu)

    def _get_info(self):
        bus_v  = self._bus_voltage_map()
        v_vals = [bus_v.get(b, 1.0) for b in self.config.dist_buses]
        violations = [b for b, v in zip(self.config.dist_buses, v_vals)
                      if v < self.v_min or v > self.v_max]
        c_safety = sum(
            max(0.0, v - self.v_max) + max(0.0, self.v_min - v)
            for v in v_vals
        )
        losses_kw = dss.Circuit.Losses()[0] / 1000.0
        t_idx  = min(max(self._t - 1, 0), self.episode_steps - 1)
        load_kw = self.config.total_base_load_kw * float(self._load_profile[t_idx])
        losses_pu = losses_kw / max(load_kw, 1.0)
        return {
            "v_min":           float(min(v_vals)),
            "v_max":           float(max(v_vals)),
            "n_violations":    len(violations),
            "violation_buses": violations,
            "losses_kw":       losses_kw,
            "timestep":        self._t,
            "c_safety":        float(c_safety),
            "r_task":          float(-self.beta * losses_pu),
        }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _mat_str(vals, n):
    parts, idx = [], 0
    for row in range(n):
        row_vals = " ".join(f"{vals[idx + col]:.6f}" for col in range(row + 1))
        parts.append(row_vals)
        idx += row + 1
    return "[" + " |".join(parts) + "]"

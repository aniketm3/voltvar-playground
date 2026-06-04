"""OpenDSS gymnasium environment for Volt-VAR control on the IEEE 13-bus feeder."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import gymnasium as gym
from gymnasium import spaces
from opendssdirect import dss

from volt_var_env.profiles import solar_profile, load_profile

# ── Static feeder configuration ─────────────────────────────────────────────

# Distribution buses whose voltages enter the observation (excludes source bus 650)
_DIST_BUSES = [
    "632", "633", "634", "645", "646",
    "671", "684", "611", "652", "680", "692", "675",
]

# PV inverter names and apparent-power ratings (kVA)
_PV_NAMES = ["PV675", "PV680", "PV611", "PV652"]
_PV_KVA   = [500.0,   400.0,   150.0,   150.0]

# Base loads: {OpenDSS_load_name: (kW, kVAR)}
_BASE_LOADS: dict[str, tuple[float, float]] = {
    "S634a": (160.0, 110.0), "S634b": (120.0,  90.0), "S634c": (120.0,  90.0),
    "S645":  (170.0, 125.0), "S646":  (230.0, 132.0),
    "S652":  (128.0,  86.0),
    "S671":  (1155.0, 660.0),
    "S675a": (485.0, 190.0), "S675b": ( 68.0,  60.0), "S675c": (290.0, 212.0),
    "S611":  (170.0,  80.0), "S692":  (170.0, 151.0),
    "S633a": ( 17.0,  10.0), "S633b": ( 66.0,  38.0), "S633c": (117.0,  68.0),
}
_TOTAL_BASE_LOAD_KW = sum(kw for kw, _ in _BASE_LOADS.values())

# Base linecode impedances for domain randomization.
# "R"/"X" are the lower-triangular elements of the Z matrix (ohm/mile).
_BASE_LINECODES: dict[str, dict] = {
    "601": {"nphases": 3,
            "R": [0.3465, 0.1560, 0.3375, 0.1580, 0.1535, 0.3414],
            "X": [1.0179, 0.5017, 1.0478, 0.4236, 0.3849, 1.0348]},
    "602": {"nphases": 3,
            "R": [0.7526, 0.1580, 0.7475, 0.1560, 0.1535, 0.7436],
            "X": [1.1814, 0.4236, 1.1983, 0.5017, 0.3849, 1.2112]},
    "603": {"nphases": 2,
            "R": [1.3238, 0.2066, 1.3294],
            "X": [1.3569, 0.4591, 1.3471]},
    "604": {"nphases": 2,
            "R": [1.3238, 0.2066, 1.3294],
            "X": [1.3569, 0.4591, 1.3471]},
    "605": {"nphases": 1, "R": [1.3292], "X": [1.3475]},
    "606": {"nphases": 3,
            "R": [0.7982, 0.3192, 0.7891, 0.2849, 0.3192, 0.7982],
            "X": [0.4463, 0.0328, 0.4041, -0.0143, 0.0328, 0.4463]},
    "607": {"nphases": 1, "R": [1.3425], "X": [0.5124]},
}

# Base capacitor ratings (kVAR)
_BASE_CAPS: dict[str, float] = {"C675": 600.0, "C611": 100.0}


# ── Domain-randomisation configuration ──────────────────────────────────────

@dataclass
class DomainRandomConfig:
    """Selects which parameters are re-sampled at every episode reset."""

    randomize_solar_load: bool = False
    randomize_grid_params: bool = False

    # Uniform draw ranges
    solar_scale_range: tuple[float, float] = (0.5, 1.5)
    load_scale_range:  tuple[float, float] = (0.7, 1.3)
    load_noise_std:    float = 0.05   # additive per-load fraction noise

    line_r_scale_range: tuple[float, float] = (0.8, 1.2)
    line_x_scale_range: tuple[float, float] = (0.8, 1.2)
    cap_scale_range:    tuple[float, float] = (0.5, 1.5)


# ── Environment ──────────────────────────────────────────────────────────────

class VoltVAREnv(gym.Env):
    """Gymnasium environment for Volt-VAR control on the IEEE 13-bus feeder.

    Observation (17-dim float32):
        v[0:12]   per-bus voltage magnitude in pu for each distribution bus
        p[12:16]  PV active-power output in pu of rated kVA  (0..1)
        t[16]     time-of-day normalised to [0, 1]

    Action (4-dim float32 in [-1, 1]):
        Normalised reactive-power setpoints for PV675, PV680, PV611, PV652.
        Mapped to [-kVA, +kVA] kVAR before being written to OpenDSS.

    Reward:
        -alpha * Σ_bus voltage_violation²  -  beta * total_losses / base_load
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        circuit_path: str | Path,
        dr_config: Optional[DomainRandomConfig] = None,
        episode_steps: int = 96,
        alpha: float = 10.0,
        beta: float = 1.0,
        v_min: float = 0.95,
        v_max: float = 1.05,
    ):
        super().__init__()
        self.circuit_path = Path(circuit_path).resolve()
        self.dr_config = dr_config or DomainRandomConfig()
        self.episode_steps = episode_steps
        self.alpha = alpha
        self.beta = beta
        self.v_min = v_min
        self.v_max = v_max

        n_bus = len(_DIST_BUSES)
        n_pv  = len(_PV_NAMES)
        obs_dim = n_bus + n_pv + 1

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
        self._solar_profile: np.ndarray = np.ones(episode_steps, dtype=np.float32)
        self._load_profile:  np.ndarray = np.ones(episode_steps, dtype=np.float32)
        self._per_load_noise: dict[str, float] = {n: 0.0 for n in _BASE_LOADS}

        # Verify the circuit loads cleanly on construction
        self._load_circuit()

    # ── Gymnasium API ────────────────────────────────────────────────────────

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[dict] = None,
    ) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        rng = self.np_random
        self._t = 0
        self._load_circuit(rng=rng)
        self._generate_profiles(rng=rng)
        self._apply_timestep()
        dss.Solution.Solve()
        return self._get_obs(), {}

    def step(
        self, action: np.ndarray
    ) -> tuple[np.ndarray, float, bool, bool, dict]:
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

    def _load_circuit(self, rng: Optional[np.random.Generator] = None) -> None:
        dss.Text.Command("Clear")
        dss.Text.Command(f"Redirect {self.circuit_path}")

        cfg = self.dr_config
        if cfg.randomize_grid_params and rng is not None:
            r_scale   = float(rng.uniform(*cfg.line_r_scale_range))
            x_scale   = float(rng.uniform(*cfg.line_x_scale_range))
            cap_scale = float(rng.uniform(*cfg.cap_scale_range))
            self._apply_grid_randomization(r_scale, x_scale, cap_scale)

        dss.Solution.Solve()

    def _apply_grid_randomization(
        self, r_scale: float, x_scale: float, cap_scale: float
    ) -> None:
        for code, data in _BASE_LINECODES.items():
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
        for cap_name, base_kvar in _BASE_CAPS.items():
            dss.Text.Command(
                f"Edit Capacitor.{cap_name} kvar={base_kvar * cap_scale:.2f}"
            )

    # ── Profile management ───────────────────────────────────────────────────

    def _generate_profiles(self, rng: Optional[np.random.Generator] = None) -> None:
        cfg = self.dr_config
        if cfg.randomize_solar_load and rng is not None:
            s_scale   = float(rng.uniform(*cfg.solar_scale_range))
            l_scale   = float(rng.uniform(*cfg.load_scale_range))
            noise_std = cfg.load_noise_std
        else:
            s_scale = l_scale = 1.0
            noise_std = 0.0

        self._solar_profile = solar_profile(
            self.episode_steps, scale=s_scale, noise_std=noise_std, rng=rng
        )
        self._load_profile = load_profile(
            self.episode_steps, scale=l_scale, noise_std=noise_std, rng=rng
        )

        if rng is not None and noise_std > 0:
            self._per_load_noise = {
                n: float(rng.normal(0.0, noise_std)) for n in _BASE_LOADS
            }
        else:
            self._per_load_noise = {n: 0.0 for n in _BASE_LOADS}

    def _apply_timestep(self) -> None:
        irr       = float(self._solar_profile[self._t])
        load_mult = float(self._load_profile[self._t])

        for pv_name in _PV_NAMES:
            dss.Text.Command(f"Edit PVSystem.{pv_name} irradiance={irr:.4f}")

        for load_name, (kw_base, kvar_base) in _BASE_LOADS.items():
            mult = max(0.0, load_mult + self._per_load_noise[load_name])
            dss.Text.Command(
                f"Edit Load.{load_name} "
                f"kw={kw_base * mult:.2f} kvar={kvar_base * mult:.2f}"
            )

    # ── Action application ───────────────────────────────────────────────────

    def _set_pv_kvar(self, action: np.ndarray) -> None:
        for pv_name, act, kva in zip(_PV_NAMES, action, _PV_KVA):
            dss.Text.Command(f"Edit PVSystem.{pv_name} kvar={float(act) * kva:.2f}")

    # ── Observation and reward ───────────────────────────────────────────────

    def _bus_voltage_map(self) -> dict[str, float]:
        """Return {bus: voltage_pu} using AllBusNames / AllBusMagPu."""
        names = [n.lower() for n in dss.Circuit.AllBusNames()]
        volts = list(dss.Circuit.AllBusMagPu())
        return dict(zip(names, volts))

    def _get_obs(self) -> np.ndarray:
        bus_v = self._bus_voltage_map()
        volt_vec = np.array(
            [bus_v.get(b, 1.0) for b in _DIST_BUSES], dtype=np.float32
        )
        pv_p = np.array(self._pv_active_power_pu(), dtype=np.float32)
        t_norm = np.array([self._t / self.episode_steps], dtype=np.float32)
        return np.concatenate([volt_vec, pv_p, t_norm])

    def _pv_active_power_pu(self) -> list[float]:
        result = []
        for pv_name, kva in zip(_PV_NAMES, _PV_KVA):
            dss.PVsystems.Name(pv_name)
            result.append(abs(dss.PVsystems.kW()) / kva)
        return result

    def _compute_reward(self) -> float:
        bus_v = self._bus_voltage_map()
        volt_penalty = sum(
            max(0.0, v - self.v_max) ** 2 + max(0.0, self.v_min - v) ** 2
            for v in bus_v.values()
        )
        losses_kw = dss.Circuit.Losses()[0] / 1000.0
        t_idx = min(max(self._t - 1, 0), self.episode_steps - 1)
        load_kw = _TOTAL_BASE_LOAD_KW * float(self._load_profile[t_idx])
        losses_pu = losses_kw / max(load_kw, 1.0)
        return float(-self.alpha * volt_penalty - self.beta * losses_pu)

    def _get_info(self) -> dict:
        bus_v = self._bus_voltage_map()
        v_vals = [bus_v.get(b, 1.0) for b in _DIST_BUSES]
        violations = [b for b, v in zip(_DIST_BUSES, v_vals)
                      if v < self.v_min or v > self.v_max]
        c_safety = sum(
            max(0.0, v - self.v_max) + max(0.0, self.v_min - v)
            for v in v_vals
        )
        losses_kw = dss.Circuit.Losses()[0] / 1000.0
        t_idx = min(max(self._t - 1, 0), self.episode_steps - 1)
        load_kw = _TOTAL_BASE_LOAD_KW * float(self._load_profile[t_idx])
        losses_pu = losses_kw / max(load_kw, 1.0)
        return {
            "v_min": float(min(v_vals)),
            "v_max": float(max(v_vals)),
            "n_violations": len(violations),
            "violation_buses": violations,
            "losses_kw": losses_kw,
            "timestep": self._t,
            "c_safety": float(c_safety),
            "r_task": float(-self.beta * losses_pu),
        }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _mat_str(vals: list[float], n: int) -> str:
    """Format lower-triangular matrix values as an OpenDSS Rmatrix/Xmatrix string."""
    parts, idx = [], 0
    for row in range(n):
        row_vals = " ".join(f"{vals[idx + col]:.6f}" for col in range(row + 1))
        parts.append(row_vals)
        idx += row + 1
    return "[" + " |".join(parts) + "]"

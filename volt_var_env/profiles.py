"""Synthetic daily solar-irradiance and load profiles for episode generation."""

from __future__ import annotations

import numpy as np


def solar_profile(
    n_steps: int = 96,
    scale: float = 1.0,
    noise_std: float = 0.05,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Synthetic daily solar irradiance profile in [0, 1].

    Sinusoidal sunrise-to-sunset envelope with multiplicative cloud noise.
    Peak at solar noon (midpoint of the episode).
    """
    if rng is None:
        rng = np.random.default_rng()
    t = np.linspace(0, np.pi, n_steps)
    base = np.sin(t)  # zero at dawn/dusk, 1.0 at noon
    # Multiplicative noise — clouds reduce irradiance, never increase it
    cloud_noise = rng.normal(0.0, noise_std, n_steps)
    profile = np.clip(base * (1.0 + cloud_noise), 0.0, 1.0) * scale
    return profile.astype(np.float32)


def load_profile(
    n_steps: int = 96,
    scale: float = 1.0,
    noise_std: float = 0.05,
    rng: np.random.Generator | None = None,
) -> np.ndarray:
    """Synthetic daily residential load profile (normalised, roughly 0.3–1.0).

    Dual-peak shape: moderate morning rise (~8 AM) and a larger evening peak
    (~7 PM), connected by a midday dip that coincides with solar peak.
    """
    if rng is None:
        rng = np.random.default_rng()

    # Time in [0, 2π) mapping to 0:00–24:00
    t = np.linspace(0, 2 * np.pi, n_steps, endpoint=False)
    morning_peak = 2 * np.pi * 8 / 24   # 8 AM
    evening_peak = 2 * np.pi * 19 / 24  # 7 PM

    morning = np.exp(-0.5 * ((t - morning_peak) / 0.45) ** 2)
    evening = np.exp(-0.5 * ((t - evening_peak) / 0.55) ** 2)
    base = 0.35 + 0.30 * morning + 0.55 * evening

    noise = rng.normal(0.0, noise_std, n_steps)
    profile = np.clip(base + noise, 0.1, 1.8) * scale
    return profile.astype(np.float32)

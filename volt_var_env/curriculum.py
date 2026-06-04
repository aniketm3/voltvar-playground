"""Curriculum domain-randomisation callback."""
from __future__ import annotations

from stable_baselines3.common.callbacks import BaseCallback
from volt_var_env.env import VoltVAREnv, DomainRandomConfig

# Three phases: (step_threshold, DomainRandomConfig kwargs)
_PHASES = [
    (30_000,       dict(randomize_solar_load=False, randomize_grid_params=False)),
    (80_000,       dict(randomize_solar_load=True,  randomize_grid_params=False,
                        solar_scale_range=(0.85, 1.15), load_scale_range=(0.85, 1.15),
                        load_noise_std=0.02)),
    (float("inf"), dict(randomize_solar_load=True,  randomize_grid_params=True,
                        solar_scale_range=(0.5, 1.5), load_scale_range=(0.7, 1.3),
                        load_noise_std=0.05)),
]


class CurriculumDRCallback(BaseCallback):
    """Progressively widens DR ranges as training progresses.

    Checks ``self.num_timesteps`` at each environment step and updates
    ``train_env.dr_config`` when crossing a phase threshold.  Phase indices
    are tracked to avoid repeated updates.
    """

    def __init__(self, train_env: VoltVAREnv, verbose: int = 1) -> None:
        super().__init__(verbose=verbose)
        self.train_env = train_env
        self._current_phase: int = -1  # no phase applied yet

    def _on_step(self) -> bool:
        for phase_idx, (threshold, kwargs) in enumerate(_PHASES):
            if self.num_timesteps < threshold:
                # This is the phase we belong to; apply if new.
                if phase_idx != self._current_phase:
                    self.train_env.dr_config = DomainRandomConfig(**kwargs)
                    self._current_phase = phase_idx
                    if self.verbose >= 1:
                        print(
                            f"[CurriculumDRCallback] step={self.num_timesteps:,} "
                            f"→ entering phase {phase_idx} "
                            f"(solar_load={kwargs['randomize_solar_load']}, "
                            f"grid={kwargs['randomize_grid_params']})"
                        )
                break
        return True

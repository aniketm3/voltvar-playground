"""Lagrangian relaxation wrapper and callback for constrained SAC."""

from __future__ import annotations
import numpy as np
import gymnasium as gym
from stable_baselines3.common.callbacks import BaseCallback


class LagrangianWrapper(gym.Wrapper):
    """Replaces env reward with:  r = r_task - lambda * c_safety

    ``lambda_val`` is updated externally by :class:`LagrangianCallback`.

    The wrapped environment must expose ``r_task`` (the losses-only reward
    component) and ``c_safety`` (sum of squared voltage violations) in the
    ``info`` dict returned by ``step()``.  Both fields are present in
    :class:`~volt_var_env.env.VoltVAREnv` by default.
    """

    def __init__(self, env: gym.Env, lambda_init: float = 0.5):
        super().__init__(env)
        self.lambda_val = float(lambda_init)

    def step(self, action):
        obs, _, terminated, truncated, info = self.env.step(action)
        reward = info["r_task"] - self.lambda_val * info["c_safety"]
        info["lambda"] = self.lambda_val
        return obs, float(reward), terminated, truncated, info


class LagrangianCallback(BaseCallback):
    """Updates lambda via gradient ascent on the Lagrangian dual.

    Every ``update_freq`` environment steps the callback computes the
    average safety cost collected since the last update and applies:

        lambda  <-  max(0, lambda + lr * (avg_c_safety - epsilon))

    When violations exceed the tolerance ``epsilon``, ``lambda`` grows and
    violations become more expensive in the reward signal.  When violations
    are within tolerance, ``lambda`` shrinks so the agent can focus on
    minimising losses.
    """

    def __init__(
        self,
        wrapper: LagrangianWrapper,
        lr_lambda: float = 1e-3,
        epsilon: float = 1e-4,
        update_freq: int = 1000,
        log_csv: str | None = None,
        verbose: int = 0,
    ):
        super().__init__(verbose)
        self.wrapper = wrapper
        self.lr_lambda = lr_lambda
        self.epsilon = epsilon
        self.update_freq = update_freq
        self.log_csv = log_csv
        self._violations: list[float] = []
        self._csv_file = None
        self._csv_writer = None

    def _on_training_start(self) -> None:
        if self.log_csv:
            import csv
            from pathlib import Path
            Path(self.log_csv).parent.mkdir(parents=True, exist_ok=True)
            self._csv_file = open(self.log_csv, "w", newline="")
            self._csv_writer = csv.writer(self._csv_file)
            self._csv_writer.writerow(["timestep", "lambda", "avg_c_safety"])

    def _on_training_end(self) -> None:
        if self._csv_file:
            self._csv_file.close()

    def _on_step(self) -> bool:
        for info in self.locals.get("infos", []):
            if "c_safety" in info:
                self._violations.append(info["c_safety"])

        if self.n_calls % self.update_freq == 0 and self._violations:
            avg_c = float(np.mean(self._violations))
            old = self.wrapper.lambda_val
            self.wrapper.lambda_val = max(
                0.0, old + self.lr_lambda * (avg_c - self.epsilon)
            )
            self._violations.clear()

            if self._csv_writer:
                self._csv_writer.writerow(
                    [self.num_timesteps, round(self.wrapper.lambda_val, 6), round(avg_c, 6)]
                )

            if self.verbose >= 1:
                print(
                    f"[λ] step={self.n_calls:>8d}  avg_c={avg_c:.5f}  "
                    f"lambda {old:.4f} -> {self.wrapper.lambda_val:.4f}"
                )
        return True

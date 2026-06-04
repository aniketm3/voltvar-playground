"""CLI entry points for volt-VAR-control."""

from __future__ import annotations

import argparse
from pathlib import Path

DEFAULT_CIRCUIT = Path(__file__).parents[1] / "circuits" / "ieee13.dss"

_DR_CONDITIONS = ("none", "solar_load", "grid", "both")


def _make_dr_config(condition: str):
    from volt_var_env import DomainRandomConfig
    return DomainRandomConfig(
        randomize_solar_load=condition in ("solar_load", "both"),
        randomize_grid_params=condition in ("grid", "both"),
    )


def _tensorboard_log(out_dir: Path) -> str | None:
    try:
        import tensorboard  # noqa: F401
    except ImportError:
        return None
    return str(out_dir / "tb")


# ── vvc-test ─────────────────────────────────────────────────────────────────

def test_env():
    """Smoke-test the VoltVAREnv with random actions for one episode."""
    parser = argparse.ArgumentParser(description="Smoke-test VoltVAREnv")
    parser.add_argument("--circuit", default=str(DEFAULT_CIRCUIT))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dr-solar-load", action="store_true")
    parser.add_argument("--dr-grid", action="store_true")
    args = parser.parse_args()

    from volt_var_env import VoltVAREnv, DomainRandomConfig

    dr = DomainRandomConfig(
        randomize_solar_load=args.dr_solar_load,
        randomize_grid_params=args.dr_grid,
    )
    env = VoltVAREnv(Path(args.circuit), dr_config=dr)
    obs, _ = env.reset(seed=args.seed)

    print(f"Circuit : {args.circuit}")
    print(f"Obs dim : {obs.shape[0]}  |  Action dim : {env.action_space.shape[0]}")
    print(f"DR      : solar/load={args.dr_solar_load}  grid={args.dr_grid}")
    print(f"\n{'t':>4}  {'v_min':>7}  {'v_max':>7}  {'viols':>5}  {'losses kW':>10}  {'reward':>8}")
    print("-" * 55)

    total_reward = 0.0
    for step in range(env.episode_steps):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        total_reward += reward
        if step % 12 == 0:
            print(
                f"{step:4d}  {info['v_min']:7.4f}  {info['v_max']:7.4f}"
                f"  {info['n_violations']:5d}  {info['losses_kw']:10.1f}  {reward:8.4f}"
            )
        if terminated or truncated:
            break

    print("-" * 55)
    print(f"Total reward: {total_reward:.3f}")


# ── vvc-train ─────────────────────────────────────────────────────────────────

def train_sac():
    """Train an SAC agent for Volt-VAR control."""
    parser = argparse.ArgumentParser(description="Train SAC agent for Volt-VAR control")
    parser.add_argument(
        "--condition", choices=_DR_CONDITIONS, default="none",
        help="Domain-randomisation condition: none | solar_load | grid | both",
    )
    parser.add_argument("--timesteps", type=int, default=200_000,
                        help="Total environment steps")
    parser.add_argument("--circuit", default=str(DEFAULT_CIRCUIT))
    parser.add_argument("--out", default="results",
                        help="Output directory (model saved under out/sac_<condition>/)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--eval-freq", type=int, default=10_000,
                        help="Evaluate agent every N environment steps")
    parser.add_argument("--n-eval-episodes", type=int, default=5)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--batch-size", type=int, default=256)
    args = parser.parse_args()

    from stable_baselines3 import SAC
    from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
    from volt_var_env import VoltVAREnv, DomainRandomConfig

    out_dir = Path(args.out) / f"sac_{args.condition}"
    out_dir.mkdir(parents=True, exist_ok=True)

    circuit = Path(args.circuit)
    train_env = VoltVAREnv(circuit, dr_config=_make_dr_config(args.condition))
    # Always evaluate on the fixed (no-DR) environment
    eval_env  = VoltVAREnv(circuit, dr_config=DomainRandomConfig())

    checkpoint_cb = CheckpointCallback(
        save_freq=args.eval_freq,
        save_path=str(out_dir / "checkpoints"),
        name_prefix=f"sac_{args.condition}",
        verbose=0,
    )
    eval_cb = EvalCallback(
        eval_env,
        best_model_save_path=str(out_dir),
        log_path=str(out_dir / "eval_logs"),
        eval_freq=args.eval_freq,
        n_eval_episodes=args.n_eval_episodes,
        deterministic=True,
        verbose=1,
    )

    model = SAC(
        "MlpPolicy",
        train_env,
        verbose=1,
        seed=args.seed,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        gamma=0.99,
        tau=0.005,
        ent_coef="auto",
        tensorboard_log=_tensorboard_log(out_dir),
    )

    print(f"Training SAC  condition={args.condition}  steps={args.timesteps:,}")
    print(f"Output dir : {out_dir}")
    model.learn(total_timesteps=args.timesteps, callback=[checkpoint_cb, eval_cb])
    model.save(str(out_dir / "final_model"))
    print(f"\nSaved final model → {out_dir / 'final_model.zip'}")


# ── vvc-train-lagrangian ──────────────────────────────────────────────────────

def train_lagrangian_sac():
    """Train a Lagrangian-constrained SAC agent for Volt-VAR control."""
    parser = argparse.ArgumentParser(
        description="Train Lagrangian SAC agent for Volt-VAR control"
    )
    parser.add_argument(
        "--condition", choices=_DR_CONDITIONS, default="none",
        help="Domain-randomisation condition: none | solar_load | grid | both",
    )
    parser.add_argument("--timesteps", type=int, default=200_000,
                        help="Total environment steps")
    parser.add_argument("--circuit", default=str(DEFAULT_CIRCUIT))
    parser.add_argument("--out", default="results",
                        help="Output directory (model saved under out/lag_sac_<condition>/)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--eval-freq", type=int, default=10_000,
                        help="Evaluate agent every N environment steps")
    parser.add_argument("--n-eval-episodes", type=int, default=5)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr-lambda", type=float, default=1e-3,
                        help="Learning rate for the Lagrange multiplier")
    parser.add_argument("--lambda-init", type=float, default=0.5,
                        help="Initial value of the Lagrange multiplier")
    args = parser.parse_args()

    from stable_baselines3 import SAC
    from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
    from volt_var_env import VoltVAREnv, DomainRandomConfig
    from volt_var_env.lagrangian import LagrangianWrapper, LagrangianCallback

    out_dir = Path(args.out) / f"lag_sac_{args.condition}"
    out_dir.mkdir(parents=True, exist_ok=True)

    circuit = Path(args.circuit)
    train_env_base = VoltVAREnv(circuit, dr_config=_make_dr_config(args.condition))
    train_env = LagrangianWrapper(train_env_base, lambda_init=args.lambda_init)
    # Always evaluate on the plain (no-DR) environment so reward is standard
    eval_env = VoltVAREnv(circuit, dr_config=DomainRandomConfig())

    checkpoint_cb = CheckpointCallback(
        save_freq=args.eval_freq,
        save_path=str(out_dir / "checkpoints"),
        name_prefix=f"lag_sac_{args.condition}",
        verbose=0,
    )
    eval_cb = EvalCallback(
        eval_env,
        best_model_save_path=str(out_dir),
        log_path=str(out_dir / "eval_logs"),
        eval_freq=args.eval_freq,
        n_eval_episodes=args.n_eval_episodes,
        deterministic=True,
        verbose=1,
    )
    lag_cb = LagrangianCallback(train_env, lr_lambda=args.lr_lambda, verbose=1)

    model = SAC(
        "MlpPolicy",
        train_env,
        verbose=1,
        seed=args.seed,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        gamma=0.99,
        tau=0.005,
        ent_coef="auto",
        tensorboard_log=_tensorboard_log(out_dir),
    )

    print(f"Training Lagrangian SAC  condition={args.condition}  steps={args.timesteps:,}")
    print(f"Output dir : {out_dir}")
    model.learn(total_timesteps=args.timesteps, callback=[checkpoint_cb, eval_cb, lag_cb])
    model.save(str(out_dir / "final_model"))
    print(f"\nSaved final model → {out_dir / 'final_model.zip'}")


# ── vvc-train-curriculum ──────────────────────────────────────────────────────

def train_curriculum_sac():
    """Train a Lagrangian SAC agent with curriculum domain randomisation."""
    parser = argparse.ArgumentParser(
        description="Train Lagrangian SAC with curriculum DR for Volt-VAR control"
    )
    parser.add_argument("--timesteps", type=int, default=200_000,
                        help="Total environment steps")
    parser.add_argument("--circuit", default=str(DEFAULT_CIRCUIT))
    parser.add_argument("--out", default="results",
                        help="Output directory (model saved under out/lag_sac_curriculum/)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--eval-freq", type=int, default=10_000,
                        help="Evaluate agent every N environment steps")
    parser.add_argument("--n-eval-episodes", type=int, default=5)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--lr-lambda", type=float, default=1e-3,
                        help="Learning rate for the Lagrange multiplier")
    parser.add_argument("--lambda-init", type=float, default=0.5,
                        help="Initial value of the Lagrange multiplier")
    args = parser.parse_args()

    from stable_baselines3 import SAC
    from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
    from volt_var_env import VoltVAREnv, DomainRandomConfig
    from volt_var_env.lagrangian import LagrangianWrapper, LagrangianCallback
    from volt_var_env.curriculum import CurriculumDRCallback

    out_dir = Path(args.out) / "lag_sac_curriculum"
    out_dir.mkdir(parents=True, exist_ok=True)

    circuit = Path(args.circuit)
    # Start with no DR; curriculum callback will widen ranges progressively
    initial_dr = DomainRandomConfig(
        randomize_solar_load=False, randomize_grid_params=False
    )
    train_env_base = VoltVAREnv(circuit, dr_config=initial_dr)
    train_env = LagrangianWrapper(train_env_base, lambda_init=args.lambda_init)
    # Evaluate on the plain (no-DR) environment
    eval_env = VoltVAREnv(circuit, dr_config=DomainRandomConfig())

    checkpoint_cb = CheckpointCallback(
        save_freq=args.eval_freq,
        save_path=str(out_dir / "checkpoints"),
        name_prefix="lag_sac_curriculum",
        verbose=0,
    )
    eval_cb = EvalCallback(
        eval_env,
        best_model_save_path=str(out_dir),
        log_path=str(out_dir / "eval_logs"),
        eval_freq=args.eval_freq,
        n_eval_episodes=args.n_eval_episodes,
        deterministic=True,
        verbose=1,
    )
    lag_cb = LagrangianCallback(train_env, lr_lambda=args.lr_lambda, verbose=1)
    curriculum_cb = CurriculumDRCallback(train_env_base, verbose=1)

    model = SAC(
        "MlpPolicy",
        train_env,
        verbose=1,
        seed=args.seed,
        learning_rate=args.learning_rate,
        batch_size=args.batch_size,
        gamma=0.99,
        tau=0.005,
        ent_coef="auto",
        tensorboard_log=_tensorboard_log(out_dir),
    )

    print(f"Training Lagrangian SAC + curriculum DR  steps={args.timesteps:,}")
    print(f"Output dir : {out_dir}")
    model.learn(
        total_timesteps=args.timesteps,
        callback=[checkpoint_cb, eval_cb, lag_cb, curriculum_cb],
    )
    model.save(str(out_dir / "final_model"))
    print(f"\nSaved final model → {out_dir / 'final_model.zip'}")


# ── vvc-eval ──────────────────────────────────────────────────────────────────

def eval_policy():
    """Evaluate a trained SAC model or a baseline controller."""
    parser = argparse.ArgumentParser(description="Evaluate a policy on VoltVAREnv")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--model", help="Path to a saved SAC model (.zip, omit extension)")
    group.add_argument(
        "--baseline", choices=["droop", "zero", "mpc"],
        help="Built-in baseline controller",
    )
    parser.add_argument(
        "--condition", choices=_DR_CONDITIONS, default="none",
        help="DR condition for the evaluation environment",
    )
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--circuit", default=str(DEFAULT_CIRCUIT))
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    import numpy as np
    from volt_var_env import VoltVAREnv
    from volt_var_env.baselines import DroopController, ZeroController

    env = VoltVAREnv(Path(args.circuit), dr_config=_make_dr_config(args.condition))

    if args.model:
        from stable_baselines3 import SAC
        policy = SAC.load(args.model, env=env)
        policy_name = Path(args.model).name
    elif args.baseline == "droop":
        policy = DroopController()
        policy_name = "droop"
    elif args.baseline == "mpc":
        from volt_var_env.mpc import MPCController
        policy = MPCController(v_min=env.v_min, v_max=env.v_max)
        policy_name = "mpc"
    else:
        policy = ZeroController()
        policy_name = "zero"

    print(f"Policy    : {policy_name}")
    print(f"Condition : {args.condition}")
    print(f"Episodes  : {args.episodes}")
    print()

    ep_rewards, ep_violations, ep_losses = [], [], []

    for ep in range(args.episodes):
        obs, _ = env.reset(seed=args.seed + ep)
        total_r, total_v, total_l = 0.0, 0, 0.0
        while True:
            action, _ = policy.predict(obs, deterministic=True)
            obs, reward, terminated, truncated, info = env.step(action)
            total_r += reward
            total_v += info["n_violations"]
            total_l += info["losses_kw"]
            if terminated or truncated:
                break
        ep_rewards.append(total_r)
        ep_violations.append(total_v)
        ep_losses.append(total_l / env.episode_steps)

    r  = np.array(ep_rewards)
    vi = np.array(ep_violations)
    lo = np.array(ep_losses)

    print(f"{'Metric':<25} {'Mean':>10} {'Std':>10} {'Min':>10} {'Max':>10}")
    print("-" * 65)
    print(f"{'Episode reward':<25} {r.mean():10.3f} {r.std():10.3f} {r.min():10.3f} {r.max():10.3f}")
    print(f"{'Total violations':<25} {vi.mean():10.1f} {vi.std():10.1f} {vi.min():10.0f} {vi.max():10.0f}")
    print(f"{'Avg losses (kW)':<25} {lo.mean():10.2f} {lo.std():10.2f} {lo.min():10.2f} {lo.max():10.2f}")

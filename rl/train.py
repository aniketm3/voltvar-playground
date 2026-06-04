"""
Train a SAC agent for Volt-VAR control on any registered feeder.

Usage:
    uv run python rl/train.py --grid ieee33 --condition solar_load
    uv run python rl/train.py --grid res9   --condition solar_load --lagrangian
    uv run python rl/train.py --grid sub18  --condition solar_load --timesteps 300000

The trained best_model.zip is saved to:
    models/<grid_id>/sac_<condition>/best_model.zip          (standard SAC)
    models/<grid_id>/lag_sac_<condition>/best_model.zip      (--lagrangian)

Restart the backend after training to make the new policy available.

Conditions:
  none        — fixed solar/load profiles (good baseline)
  solar_load  — randomize solar scale and load each episode (recommended for new feeders)
  grid        — randomize line impedances/capacitors (only works for ieee13)
  both        — randomize everything (only works for ieee13)

Recommended per feeder:
  ieee13  — already has trained models; retrain with --condition both if needed
  ieee33  — --condition solar_load  (no linecodes defined, grid DR skipped)
  res9    — --condition solar_load
  sub18   — --condition solar_load
"""

import argparse
import sys
from pathlib import Path

REPO_ROOT  = Path(__file__).parents[1]
MODELS_DIR = REPO_ROOT / "models"
sys.path.insert(0, str(REPO_ROOT))


def main():
    parser = argparse.ArgumentParser(description="Train SAC for Volt-VAR control")
    parser.add_argument(
        "--grid", required=True,
        choices=["ieee13", "ieee33", "res9", "sub18"],
        help="Which feeder to train on",
    )
    parser.add_argument(
        "--condition", choices=["none", "solar_load", "grid", "both"],
        default="solar_load",
        help="Domain-randomisation condition (grid/both only useful for ieee13)",
    )
    parser.add_argument("--lagrangian",  action="store_true",
                        help="Use Lagrangian-constrained SAC (better voltage safety)")
    parser.add_argument("--curriculum",  action="store_true",
                        help="Use curriculum DR: start with no randomisation, widen progressively. "
                             "Implies --lagrangian.")
    parser.add_argument("--timesteps",   type=int,   default=200_000)
    parser.add_argument("--seed",        type=int,   default=0)
    parser.add_argument("--eval-freq",   type=int,   default=10_000)
    parser.add_argument("--n-eval-eps",  type=int,   default=5)
    parser.add_argument("--lr",          type=float, default=3e-4)
    parser.add_argument("--batch-size",  type=int,   default=256)
    parser.add_argument("--lr-lambda",   type=float, default=1e-3,
                        help="Lagrange multiplier learning rate (--lagrangian only)")
    parser.add_argument("--lambda-init", type=float, default=0.5,
                        help="Initial Lagrange multiplier (--lagrangian only)")
    args = parser.parse_args()
    if args.curriculum:
        args.lagrangian = True  # curriculum always uses Lagrangian

    from stable_baselines3 import SAC
    from stable_baselines3.common.callbacks import EvalCallback, CheckpointCallback
    from volt_var_env import VoltVAREnv, DomainRandomConfig
    from backend.grid_registry import GRIDS

    config = GRIDS[args.grid]

    if args.condition in ("grid", "both") and not config.base_linecodes:
        print(f"[warn] {args.grid} has no linecodes — grid DR will have no effect. "
              f"Using solar_load condition instead.")
        args.condition = "solar_load"

    dr_config = DomainRandomConfig(
        randomize_solar_load=args.condition in ("solar_load", "both"),
        randomize_grid_params=args.condition in ("grid", "both"),
    )

    prefix   = "lag_sac" if args.lagrangian else "sac"
    run_name = "lag_sac_curriculum" if args.curriculum else f"{prefix}_{args.condition}"
    out_dir  = MODELS_DIR / args.grid / run_name
    out_dir.mkdir(parents=True, exist_ok=True)

    train_env_base = VoltVAREnv(config, dr_config=dr_config)
    eval_env       = VoltVAREnv(config, dr_config=DomainRandomConfig())

    if args.curriculum:
        from volt_var_env.lagrangian import LagrangianWrapper, LagrangianCallback
        from volt_var_env.curriculum import CurriculumDRCallback
        # Curriculum starts with no DR and widens progressively — override dr_config
        train_env_base = VoltVAREnv(
            config,
            dr_config=DomainRandomConfig(randomize_solar_load=False, randomize_grid_params=False),
        )
        train_env = LagrangianWrapper(train_env_base, lambda_init=args.lambda_init)
        lag_cb        = LagrangianCallback(train_env, lr_lambda=args.lr_lambda, verbose=1)
        curriculum_cb = CurriculumDRCallback(train_env_base, verbose=1)
        extra_cbs     = [lag_cb, curriculum_cb]
    elif args.lagrangian:
        from volt_var_env.lagrangian import LagrangianWrapper, LagrangianCallback
        train_env = LagrangianWrapper(train_env_base, lambda_init=args.lambda_init)
        lag_cb    = LagrangianCallback(train_env, lr_lambda=args.lr_lambda, verbose=1)
        extra_cbs = [lag_cb]
    else:
        train_env = train_env_base
        extra_cbs = []

    eval_cb = EvalCallback(
        eval_env,
        best_model_save_path=str(out_dir),
        log_path=str(out_dir / "eval_logs"),
        eval_freq=args.eval_freq,
        n_eval_episodes=args.n_eval_eps,
        deterministic=True,
        verbose=1,
    )
    ckpt_cb = CheckpointCallback(
        save_freq=args.eval_freq,
        save_path=str(out_dir / "checkpoints"),
        name_prefix=run_name,
        verbose=0,
    )

    model = SAC(
        "MlpPolicy",
        train_env,
        verbose=1,
        seed=args.seed,
        learning_rate=args.lr,
        batch_size=args.batch_size,
        gamma=0.99,
        tau=0.005,
        ent_coef="auto",
    )

    kind = "Lag-SAC + Curriculum" if args.curriculum else ("Lagrangian SAC" if args.lagrangian else "SAC")
    print(f"\nTraining {kind}  grid={args.grid}  condition={args.condition}  "
          f"steps={args.timesteps:,}  seed={args.seed}")
    print(f"Obs dim: {config.obs_dim}   Action dim: {config.n_pv}   "
          f"Buses: {config.n_buses}   PV: {config.n_pv}")
    print(f"Output → {out_dir}\n")

    model.learn(
        total_timesteps=args.timesteps,
        callback=[eval_cb, ckpt_cb] + extra_cbs,
    )
    model.save(str(out_dir / "final_model"))
    print(f"\nDone. Restart the backend to deploy {out_dir}/best_model.zip")


if __name__ == "__main__":
    main()

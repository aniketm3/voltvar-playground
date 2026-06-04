"""
Train a new SAC agent for Volt-VAR control on the IEEE 13-bus feeder.

Usage:
    uv run python rl/train.py --condition both --timesteps 200000 --seed 0

The trained model is saved to models/<run_name>/best_model.zip.
Swap that file out and restart the backend to deploy the new policy.

Conditions:
  none        — fixed solar/load profiles, fixed grid parameters
  solar_load  — randomize solar scale and load scale each episode
  grid        — randomize line impedances and capacitor ratings
  both        — randomize everything (most robust, recommended)
"""

import argparse
from pathlib import Path

REPO_ROOT    = Path(__file__).parents[1]
CIRCUIT_PATH = REPO_ROOT / "circuits" / "ieee13.dss"
MODELS_DIR   = REPO_ROOT / "models"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition",  choices=["none", "solar_load", "grid", "both"], default="both")
    parser.add_argument("--timesteps",  type=int,   default=200_000)
    parser.add_argument("--seed",       type=int,   default=0)
    parser.add_argument("--eval-freq",  type=int,   default=10_000)
    parser.add_argument("--n-eval-eps", type=int,   default=5)
    parser.add_argument("--lr",         type=float, default=3e-4)
    parser.add_argument("--batch-size", type=int,   default=256)
    args = parser.parse_args()

    import sys
    sys.path.insert(0, str(REPO_ROOT))

    from stable_baselines3 import SAC
    from stable_baselines3.common.callbacks import EvalCallback, CheckpointCallback
    from volt_var_env import VoltVAREnv, DomainRandomConfig

    dr_config = DomainRandomConfig(
        randomize_solar_load=args.condition in ("solar_load", "both"),
        randomize_grid_params=args.condition in ("grid", "both"),
    )

    run_name = f"sac_{args.condition}"
    out_dir  = MODELS_DIR / run_name
    out_dir.mkdir(parents=True, exist_ok=True)

    train_env = VoltVAREnv(CIRCUIT_PATH, dr_config=dr_config)
    eval_env  = VoltVAREnv(CIRCUIT_PATH, dr_config=DomainRandomConfig())

    eval_cb = EvalCallback(
        eval_env,
        best_model_save_path=str(out_dir),
        log_path=str(out_dir / "eval_logs"),
        eval_freq=args.eval_freq,
        n_eval_episodes=args.n_eval_eps,
        deterministic=True,
        verbose=1,
    )
    checkpoint_cb = CheckpointCallback(
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

    print(f"Training SAC  condition={args.condition}  steps={args.timesteps:,}")
    print(f"Output: {out_dir}")
    model.learn(total_timesteps=args.timesteps, callback=[eval_cb, checkpoint_cb])
    model.save(str(out_dir / "final_model"))
    print(f"\nDone. Deploy by restarting the backend — it loads {out_dir}/best_model.zip")


if __name__ == "__main__":
    main()

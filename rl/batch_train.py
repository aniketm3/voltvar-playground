"""
Batch training runner — reads train_runs.toml, skips completed runs.

Usage:
    uv run python rl/batch_train.py               # run queue from rl/train_runs.toml
    uv run python rl/batch_train.py --dry-run     # show plan without running anything
    uv run python rl/batch_train.py --config path/to/other.toml
"""

import argparse
import subprocess
import sys
import tomllib
from pathlib import Path

REPO_ROOT  = Path(__file__).parents[1]
MODELS_DIR = REPO_ROOT / "models"
TRAIN_PY   = REPO_ROOT / "rl" / "train.py"
DEFAULT_CFG = REPO_ROOT / "rl" / "train_runs.toml"


def model_path(grid: str, condition: str, lagrangian: bool, curriculum: bool) -> Path:
    if curriculum:
        return MODELS_DIR / grid / "lag_sac_curriculum" / "best_model.zip"
    prefix = "lag_sac" if lagrangian else "sac"
    return MODELS_DIR / grid / f"{prefix}_{condition}" / "best_model.zip"


def load_runs(config_path: Path) -> list[dict]:
    with open(config_path, "rb") as f:
        data = tomllib.load(f)
    return data.get("run", [])


def main():
    parser = argparse.ArgumentParser(description="Batch VoltVAR training runner")
    parser.add_argument("--config",  default=str(DEFAULT_CFG),
                        help="Path to TOML config (default: rl/train_runs.toml)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the plan without launching any training jobs")
    args = parser.parse_args()

    runs = load_runs(Path(args.config))
    if not runs:
        print("No [[run]] entries found in config.")
        sys.exit(0)

    pending, skipped = [], []
    for run in runs:
        grid       = run["grid"]
        condition  = run["condition"]
        lagrangian = run.get("lagrangian", False)
        curriculum = run.get("curriculum", False)
        out        = model_path(grid, condition, lagrangian, curriculum)
        if curriculum:
            label = f"{grid}  lag_sac_curriculum"
        else:
            kind  = "lag_sac" if lagrangian else "sac"
            label = f"{grid}  {kind}_{condition}"
        if out.exists():
            skipped.append(label)
        else:
            pending.append((run, label, out))

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"\n{'DRY RUN — ' if args.dry_run else ''}Training queue from {args.config}")
    print(f"  Already done ({len(skipped)}):  " + (", ".join(skipped) if skipped else "none"))
    print(f"  To train    ({len(pending)}):  " + (", ".join(l for _, l, _ in pending) if pending else "none"))
    print()

    if not pending:
        print("Nothing to do — all models already trained.")
        return

    if args.dry_run:
        print("Commands that would run:")
        for run, label, out in pending:
            print(f"  {_cmd_str(run)}")
        return

    # ── Run sequentially ─────────────────────────────────────────────────────
    total = len(pending)
    for i, (run, label, out) in enumerate(pending, 1):
        print(f"[{i}/{total}] Starting: {label}")
        print(f"        → {out}")
        print()
        cmd = _build_cmd(run)
        result = subprocess.run(cmd, cwd=str(REPO_ROOT / "backend"))
        if result.returncode != 0:
            print(f"\n[ERROR] Training failed for {label} (exit {result.returncode})")
            print("Stopping batch. Fix the error and re-run — completed runs will be skipped.\n")
            sys.exit(result.returncode)
        print(f"\n[{i}/{total}] Done: {label}\n{'─'*60}\n")

    print(f"All {total} training run(s) complete.")


def _build_cmd(run: dict) -> list[str]:
    cmd = [sys.executable, str(TRAIN_PY),
           "--grid",      run["grid"],
           "--condition", run["condition"]]
    if run.get("curriculum"):
        cmd.append("--curriculum")
    elif run.get("lagrangian"):
        cmd.append("--lagrangian")
    if "timesteps" in run:
        cmd += ["--timesteps", str(run["timesteps"])]
    if "seed" in run:
        cmd += ["--seed", str(run["seed"])]
    if "lr" in run:
        cmd += ["--lr", str(run["lr"])]
    return cmd


def _cmd_str(run: dict) -> str:
    return " ".join(_build_cmd(run)).replace(str(REPO_ROOT) + "/", "")


if __name__ == "__main__":
    main()

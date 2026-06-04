# VoltVAR Explorer

An interactive web app for exploring reinforcement learning–based Volt-VAR control on IEEE power distribution feeders. Built for CS153.

---

## What it does

Power distribution grids face growing voltage regulation challenges as rooftop solar penetration increases — overvoltage at midday peak output, undervoltage at evening load peak. Traditional droop control (IEEE 1547) is static and can't coordinate across inverters. This project trains RL agents to control reactive power injection across PV inverters on a feeder, then lets you explore their behavior interactively.

The app lets you:
- Compare RL policies (Lag-SAC, SAC, Droop, Zero-VAR) on four feeders in real time
- Scrub through the 24-hour simulation timeline and see voltage heatmaps update live
- Draw custom per-inverter weather profiles (drag hour bars to sculpt cloud cover)
- Run full-episode rollouts and inspect the min/max voltage envelope across all buses

---

## Feeders

| ID | Name | Buses | kV | Challenge |
|----|------|-------|----|-----------|
| `ieee13` | IEEE 13-Bus Feeder | 12 | 4.16 | Overvoltage under peak solar |
| `ieee33` | IEEE 33-Bus Feeder | 32 | 12.66 | End-of-feeder voltage sag under load |
| `res9` | 9-Bus Residential | 8 | 4.16 | High PV-to-load ratio, midday overvoltage |
| `sub18` | 18-Bus Suburban | 17 | 12.47 | Dual stress: over at solar peak, under at load peak |

---

## Policies

| Policy | Description |
|--------|-------------|
| `lag_sac_both` / `lag_sac_solar_load` | Lagrangian-constrained SAC — dynamically adjusts safety penalty weight to enforce voltage bounds |
| `lag_sac_curriculum` | Lag-SAC with curriculum domain randomization — trains on progressively wider weather/load distributions |
| `sac_both` / `sac_solar_load` | Standard SAC with domain randomization |
| `droop` | IEEE 1547 droop controller (baseline) |
| `zero` | Zero reactive power injection (worst-case baseline) |

---

## Architecture

```
voltvar-playground/
├── circuits/          # OpenDSS feeder definitions (.dss)
├── volt_var_env/      # Gymnasium environment wrapping OpenDSS
│   ├── env.py         # VoltVAREnv — state, action, reward
│   ├── lagrangian.py  # LagrangianWrapper + LagrangianCallback
│   └── curriculum.py  # CurriculumDRCallback
├── rl/
│   ├── train.py       # Single-run training script
│   └── batch_train.py # Queue-based batch trainer (reads train_runs.toml)
├── models/            # Trained best_model.zip files, one dir per feeder/policy
├── backend/
│   ├── main.py        # FastAPI app — /grids, /simulate
│   ├── simulator.py   # SimulationEngine: loads policies, runs OpenDSS
│   └── grid_registry.py  # GridConfig definitions and SVG layouts
└── frontend/          # React + Vite
    └── src/
        ├── App.jsx
        ├── components/
        │   ├── ControlPanel.jsx   # Per-inverter sliders + 24h drag editor
        │   ├── GridGraph.jsx      # SVG network diagram
        │   └── VoltageChart.jsx   # Bus voltage bar chart / episode envelope
        └── screens/
            └── FeedersScreen.jsx  # Landing page with feeder cards
```

**Backend:** FastAPI on `localhost:8000`. Loads one `SimulationEngine` per feeder at startup (each holds all trained policies and a live OpenDSS instance). Thread-safe via a per-feeder lock.

**Frontend:** React + Vite on `localhost:5173`. Debounced simulation calls on every control change (~200ms). Policy dropdown and time scrubber in the header; inverter controls and live metrics in the right panel.

---

## Running locally

### Backend

```bash
cd backend
uv run uvicorn main:app --reload
```

Restart after training new models to pick them up.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Training

Edit `rl/train_runs.toml` to define runs, then:

```bash
uv run python rl/batch_train.py          # run all pending jobs
uv run python rl/batch_train.py --dry-run  # preview without training
```

Completed runs (where `best_model.zip` already exists) are skipped automatically.

Single run:

```bash
uv run python rl/train.py --grid ieee33 --condition solar_load --lagrangian --timesteps 300000
```

---

## RL formulation

**State:** Bus voltages (p.u.) across all distribution buses + current timestep index.

**Action:** Normalized reactive power setpoints ∈ [−1, 1] for each PV inverter, scaled to inverter kVA rating.

**Reward:** `r = −α · Σ(voltage violations²) − β · losses_pu`

**Lagrangian extension:** Reward is replaced with `r_task − λ · c_safety`, where `c_safety` is the sum of absolute voltage deviations and `λ` is updated via dual ascent every 1000 steps:

```
λ ← max(0, λ + lr_λ · (avg_c_safety − ε))
```

**Curriculum:** Domain randomization (solar scale, load scale) starts at zero variance and widens linearly over training as the agent's eval performance improves.

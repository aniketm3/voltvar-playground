"""FastAPI backend for VoltVAR Explorer."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).parents[1]))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from grid_registry import GRIDS
from simulator import SimulationEngine

PolicyName = Literal[
    "sac_both", "sac_none", "lag_sac_both",
    "sac_solar_load", "lag_sac_solar_load",
    "lag_sac_curriculum",
    "droop", "zero",
]

_engines: dict[str, SimulationEngine] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Loading environments and models...")
    for grid_id, config in GRIDS.items():
        print(f"  [{grid_id}] loading...")
        _engines[grid_id] = SimulationEngine(config)
        print(f"  [{grid_id}] ready — policies: {_engines[grid_id].available_policies}")
    print("All engines ready.")
    yield


app = FastAPI(title="VoltVAR Explorer API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class SimulateRequest(BaseModel):
    grid_id:      str       = "ieee13"
    policy:       PolicyName = "lag_sac_both"
    mode:         str       = Field("single_step", pattern="^(single_step|full_episode)$")
    timestep:     int       = Field(48, ge=0, le=95)
    solar_scales: list[float] = Field(default_factory=lambda: [1.0, 1.0, 1.0, 1.0])
    cloud_covers: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    load_scale:   float     = Field(1.0, ge=0.1, le=2.0)


@app.get("/health")
async def health():
    return {"status": "ok", "grids_loaded": list(_engines.keys())}


@app.get("/grids")
async def list_grids():
    return [
        config.to_api_dict(_engines[gid].available_policies)
        for gid, config in GRIDS.items()
    ]


@app.post("/simulate")
async def simulate(req: SimulateRequest):
    engine = _engines.get(req.grid_id)
    if engine is None:
        raise HTTPException(404, f"Unknown grid: {req.grid_id}")
    if req.policy not in engine.available_policies:
        raise HTTPException(400, f"Policy '{req.policy}' not available for {req.grid_id}")

    n_pv = GRIDS[req.grid_id].n_pv
    solar_scales = (req.solar_scales + [1.0] * n_pv)[:n_pv]
    cloud_covers = (req.cloud_covers + [0.0] * n_pv)[:n_pv]

    if req.mode == "full_episode":
        return engine.simulate_episode(req.policy, solar_scales, cloud_covers, req.load_scale)
    return engine.simulate_step(req.policy, req.timestep, solar_scales, cloud_covers, req.load_scale)

"""FastAPI backend for VoltVAR Explorer."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from simulator import SimulationEngine, PolicyName

_engine: SimulationEngine | None = None
_executor = ThreadPoolExecutor(max_workers=1)  # OpenDSS is a singleton


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _engine
    print("Loading models and environment...")
    _engine = SimulationEngine()
    print("Ready.")
    yield
    _executor.shutdown(wait=False)


app = FastAPI(title="VoltVAR Explorer API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class SimulateRequest(BaseModel):
    policy: PolicyName = "sac_both"
    mode: str = Field("single_step", pattern="^(single_step|full_episode)$")
    timestep: int = Field(48, ge=0, le=95)
    solar_scales: list[float] = Field(default_factory=lambda: [1.0, 1.0, 1.0, 1.0])
    cloud_covers: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    load_scale: float = Field(1.0, ge=0.1, le=2.0)


@app.get("/health")
async def health():
    return {"status": "ok", "engine_ready": _engine is not None}


@app.post("/simulate")
async def simulate(req: SimulateRequest):
    if _engine is None:
        raise HTTPException(503, "Engine not ready")

    loop = asyncio.get_event_loop()

    if req.mode == "full_episode":
        result = await loop.run_in_executor(
            _executor,
            _engine.simulate_episode,
            req.policy,
            req.solar_scales,
            req.cloud_covers,
            req.load_scale,
        )
    else:
        result = await loop.run_in_executor(
            _executor,
            _engine.simulate_step,
            req.policy,
            req.timestep,
            req.solar_scales,
            req.cloud_covers,
            req.load_scale,
        )

    return result

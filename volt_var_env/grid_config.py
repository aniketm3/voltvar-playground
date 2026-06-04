"""Per-feeder configuration dataclass.

Each GridConfig fully describes one feeder: circuit file, observation/action
spaces, domain-randomisation parameters, and SVG layout for the frontend.
Adding a new feeder = adding one GridConfig instance to grid_registry.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).parents[1]


@dataclass
class GridConfig:
    # ── Identity ──────────────────────────────────────────────────────────────
    id:          str
    name:        str
    description: str
    voltage_kv:  float

    # ── Circuit ───────────────────────────────────────────────────────────────
    circuit_path: Path
    source_bus:   str

    # ── Observation / action spaces ───────────────────────────────────────────
    dist_buses:      list[str]          # buses whose voltages enter the obs (ordered)
    pv_names:        list[str]          # PVSystem names in OpenDSS (action order)
    pv_kva:          list[float]        # rated kVA per inverter
    pv_bus_obs_idx:  list[int]          # index of each PV's bus in dist_buses

    # ── Base electrical parameters ────────────────────────────────────────────
    base_loads:     dict[str, tuple[float, float]]  # {load_name: (kW, kVAR)}
    base_linecodes: dict[str, dict]                 # for grid DR; empty = no grid DR
    base_caps:      dict[str, float]                # capacitor ratings for DR

    # ── SVG layout (passed through to frontend) ───────────────────────────────
    # node_positions: {bus_name: {"x": int, "y": int}}
    node_positions: dict[str, dict] = field(default_factory=dict)
    # edges: [["fromBus", "toBus"], ["fromBus", "toBus", "transformer"], ...]
    edges: list = field(default_factory=list)

    # ── Derived properties ────────────────────────────────────────────────────
    @property
    def n_buses(self) -> int:
        return len(self.dist_buses)

    @property
    def n_pv(self) -> int:
        return len(self.pv_names)

    @property
    def obs_dim(self) -> int:
        return self.n_buses + self.n_pv + 1

    @property
    def total_base_load_kw(self) -> float:
        return sum(kw for kw, _ in self.base_loads.values())

    # Default scenario shown on first load
    default_timestep:    int        = 48
    default_solar_scales: list[float] = field(default_factory=lambda: [1.0, 1.0, 1.0, 1.0])
    default_cloud_covers: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0, 0.0])
    default_load_scale:  float     = 1.0

    def to_api_dict(self, available_models: list[str]) -> dict:
        """Serialise for the /grids endpoint (SVG layout included)."""
        # Map each PV name to its bus: {"PV675": "675", "PV680": "680", ...}
        pv_buses = {
            pv: self.dist_buses[idx]
            for pv, idx in zip(self.pv_names, self.pv_bus_obs_idx)
        }
        return {
            "id":               self.id,
            "name":             self.name,
            "description":      self.description,
            "voltage_kv":       self.voltage_kv,
            "n_buses":          self.n_buses,
            "n_pv":             self.n_pv,
            "source_bus":       self.source_bus,
            "pv_names":         self.pv_names,
            "pv_kva":           self.pv_kva,
            "pv_buses":         pv_buses,
            "available_models":      available_models,
            "node_positions":        self.node_positions,
            "edges":                 self.edges,
            "default_timestep":      self.default_timestep,
            "default_solar_scales":  self.default_solar_scales,
            "default_cloud_covers":  self.default_cloud_covers,
            "default_load_scale":    self.default_load_scale,
        }

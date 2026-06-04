"""Registry of available feeder configurations.

To add a new feeder:
  1. Add a .dss file under circuits/
  2. Add a GridConfig entry here with SVG layout
  3. Restart the backend — it auto-loads models from models/<grid_id>/
"""

from pathlib import Path
from volt_var_env.grid_config import GridConfig

REPO_ROOT = Path(__file__).parents[1]


# ── IEEE 13-Bus Urban Feeder ──────────────────────────────────────────────────

IEEE13 = GridConfig(
    id          = "ieee13",
    name        = "IEEE 13-Bus Feeder",
    description = "Small urban distribution feeder (4.16 kV). High source voltage causes "
                  "overvoltage under peak solar. Classic benchmark for Volt-VAR control.",
    voltage_kv  = 4.16,
    circuit_path = REPO_ROOT / "circuits" / "ieee13.dss",
    source_bus  = "650",

    dist_buses = ["632","633","634","645","646","671","684","611","652","680","692","675"],
    pv_names   = ["PV675", "PV680", "PV611", "PV652"],
    pv_kva     = [500.0, 400.0, 150.0, 150.0],
    # Which index in dist_buses corresponds to each PV's bus:
    # 675→idx 11, 680→idx 9, 611→idx 7, 652→idx 8
    pv_bus_obs_idx = [11, 9, 7, 8],

    base_loads = {
        "S634a": (160.0, 110.0), "S634b": (120.0, 90.0),  "S634c": (120.0, 90.0),
        "S645":  (170.0, 125.0), "S646":  (230.0, 132.0),
        "S652":  (128.0,  86.0),
        "S671":  (1155.0, 660.0),
        "S675a": (485.0, 190.0), "S675b": (68.0,  60.0),  "S675c": (290.0, 212.0),
        "S611":  (170.0,  80.0), "S692":  (170.0, 151.0),
        "S633a": (17.0,   10.0), "S633b": (66.0,  38.0),  "S633c": (117.0, 68.0),
    },
    base_linecodes = {
        "601": {"nphases": 3,
                "R": [0.3465,0.1560,0.3375,0.1580,0.1535,0.3414],
                "X": [1.0179,0.5017,1.0478,0.4236,0.3849,1.0348]},
        "602": {"nphases": 3,
                "R": [0.7526,0.1580,0.7475,0.1560,0.1535,0.7436],
                "X": [1.1814,0.4236,1.1983,0.5017,0.3849,1.2112]},
        "603": {"nphases": 2, "R": [1.3238,0.2066,1.3294], "X": [1.3569,0.4591,1.3471]},
        "604": {"nphases": 2, "R": [1.3238,0.2066,1.3294], "X": [1.3569,0.4591,1.3471]},
        "605": {"nphases": 1, "R": [1.3292], "X": [1.3475]},
        "606": {"nphases": 3,
                "R": [0.7982,0.3192,0.7891,0.2849,0.3192,0.7982],
                "X": [0.4463,0.0328,0.4041,-0.0143,0.0328,0.4463]},
        "607": {"nphases": 1, "R": [1.3425], "X": [0.5124]},
    },
    base_caps = {"C675": 600.0, "C611": 100.0},

    node_positions = {
        "650": {"x": 52,  "y": 220},
        "632": {"x": 180, "y": 220},
        "633": {"x": 180, "y": 115},
        "634": {"x": 180, "y": 30},
        "645": {"x": 300, "y": 115},
        "646": {"x": 415, "y": 115},
        "671": {"x": 370, "y": 220},
        "680": {"x": 510, "y": 220},
        "692": {"x": 510, "y": 315},
        "675": {"x": 510, "y": 405},
        "684": {"x": 370, "y": 315},
        "611": {"x": 260, "y": 405},
        "652": {"x": 460, "y": 405},
    },
    edges = [
        ["650","632"],
        ["632","671"],
        ["671","680"],
        ["632","633"],
        ["633","634","transformer"],
        ["632","645"],
        ["645","646"],
        ["671","684"],
        ["684","611"],
        ["684","652"],
        ["671","692","switch"],
        ["692","675"],
    ],
)


# ── IEEE 33-Bus Radial Feeder ─────────────────────────────────────────────────

_IEEE33_LOADS = {f"L{i}": None for i in range(2, 34)}
_raw_loads = {
    2:(100,60),  3:(90,40),   4:(120,80),  5:(60,30),   6:(60,20),
    7:(200,100), 8:(200,100), 9:(60,20),   10:(60,20),  11:(45,30),
    12:(60,35),  13:(60,35),  14:(120,80), 15:(60,10),  16:(60,20),
    17:(60,20),  18:(90,40),  19:(90,40),  20:(90,40),  21:(90,40),
    22:(90,40),  23:(90,50),  24:(420,200),25:(420,200),26:(60,25),
    27:(60,25),  28:(60,20),  29:(120,70), 30:(200,600),31:(150,70),
    32:(210,100),33:(60,40),
}
_IEEE33_BASE_LOADS = {f"L{k}": v for k, v in _raw_loads.items()}

# SVG layout: 720×370 viewBox
# Main trunk (buses 1-18) at y=190, x from 30 to 694, step=38
_T_X = {i: 30 + (i - 1) * 38 for i in range(1, 19)}   # trunk x positions
_IEEE33_NODE_POS = {
    # Source + main trunk
    "1":  {"x": _T_X[1],  "y": 190},
    "2":  {"x": _T_X[2],  "y": 190},
    "3":  {"x": _T_X[3],  "y": 190},
    "4":  {"x": _T_X[4],  "y": 190},
    "5":  {"x": _T_X[5],  "y": 190},
    "6":  {"x": _T_X[6],  "y": 190},
    "7":  {"x": _T_X[7],  "y": 190},
    "8":  {"x": _T_X[8],  "y": 190},
    "9":  {"x": _T_X[9],  "y": 190},
    "10": {"x": _T_X[10], "y": 190},
    "11": {"x": _T_X[11], "y": 190},
    "12": {"x": _T_X[12], "y": 190},
    "13": {"x": _T_X[13], "y": 190},
    "14": {"x": _T_X[14], "y": 190},
    "15": {"x": _T_X[15], "y": 190},
    "16": {"x": _T_X[16], "y": 190},
    "17": {"x": _T_X[17], "y": 190},
    "18": {"x": _T_X[18], "y": 190},
    # Branch 2→19–22 (upper)
    "19": {"x": 96,  "y": 120},
    "20": {"x": 128, "y": 120},
    "21": {"x": 160, "y": 120},
    "22": {"x": 192, "y": 120},
    # Branch 3→23–25 (upper, higher)
    "23": {"x": 128, "y": 62},
    "24": {"x": 160, "y": 62},
    "25": {"x": 192, "y": 62},
    # Branch 6→26–33 (lower)
    "26": {"x": 258, "y": 265},
    "27": {"x": 290, "y": 265},
    "28": {"x": 322, "y": 265},
    "29": {"x": 354, "y": 265},
    "30": {"x": 386, "y": 265},
    "31": {"x": 418, "y": 265},
    "32": {"x": 450, "y": 265},
    "33": {"x": 482, "y": 265},
}

IEEE33 = GridConfig(
    id          = "ieee33",
    name        = "IEEE 33-Bus Feeder",
    description = "Long radial distribution feeder (12.66 kV, Baran & Wu 1989). "
                  "End-of-feeder buses sag under load and spike under solar — a tougher "
                  "voltage control problem than the 13-bus.",
    voltage_kv  = 12.66,
    circuit_path = REPO_ROOT / "circuits" / "ieee33.dss",
    source_bus  = "1",

    dist_buses = [str(i) for i in range(2, 34)],   # buses 2–33 (32 buses)
    pv_names   = ["PV18", "PV22", "PV25", "PV33"],
    pv_kva     = [200.0, 150.0, 300.0, 200.0],
    # dist_buses is 2..33 (index 0..31); PV buses 18,22,25,33 → idx 16,20,23,31
    pv_bus_obs_idx = [16, 20, 23, 31],

    base_loads     = _IEEE33_BASE_LOADS,
    base_linecodes = {},   # per-line R1/X1 — grid DR not implemented for 33-bus
    base_caps      = {},

    node_positions = _IEEE33_NODE_POS,
    edges = [
        # Main trunk
        ["1","2"],["2","3"],["3","4"],["4","5"],["5","6"],
        ["6","7"],["7","8"],["8","9"],["9","10"],["10","11"],
        ["11","12"],["12","13"],["13","14"],["14","15"],["15","16"],
        ["16","17"],["17","18"],
        # Branch from 2
        ["2","19"],["19","20"],["20","21"],["21","22"],
        # Branch from 3
        ["3","23"],["23","24"],["24","25"],
        # Branch from 6
        ["6","26"],["26","27"],["27","28"],["28","29"],["29","30"],
        ["30","31"],["31","32"],["32","33"],
    ],
)


# ── Registry ──────────────────────────────────────────────────────────────────

GRIDS: dict[str, GridConfig] = {
    "ieee13": IEEE13,
    "ieee33": IEEE33,
}

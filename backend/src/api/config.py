"""
config.py
Centralized application configuration for the Margadarshak backend.

Loads settings from environment variables (with sensible defaults).
All modules should import settings from here rather than using
hardcoded values or scattered os.environ calls.
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()


@dataclass
class SumoConfig:
    """SUMO simulator settings."""
    sumo_home:   str = os.environ.get("SUMO_HOME", "/usr/share/sumo")
    binary:      str = os.environ.get("SUMO_BINARY", "sumo")
    traci_port:  int = int(os.environ.get("TRACI_PORT", "8813"))
    use_gui:     bool = os.environ.get("SUMO_GUI", "false").lower() == "true"


@dataclass
class ServerConfig:
    """FastAPI server settings."""
    host:        str = os.environ.get("HOST", "0.0.0.0")
    port:        int = int(os.environ.get("PORT", "8000"))
    reload:      bool = os.environ.get("RELOAD", "true").lower() == "true"
    log_level:   str = os.environ.get("LOG_LEVEL", "info")
    cors_origins: list = field(default_factory=lambda: ["*"])


@dataclass
class PathConfig:
    """File system paths for simulation data."""
    base_dir:        str = os.path.dirname(os.path.abspath(__file__))
    project_root:    str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../../")
    )

    @property
    def data_dir(self) -> str:
        return os.path.join(self.project_root, "data")

    @property
    def osm_raw_dir(self) -> str:
        return os.path.join(self.data_dir, "osm_raw")

    @property
    def sumo_networks_dir(self) -> str:
        return os.path.join(self.data_dir, "sumo_networks")

    @property
    def routes_dir(self) -> str:
        return os.path.join(self.data_dir, "routes")

    @property
    def configs_dir(self) -> str:
        return os.path.join(self.data_dir, "configs")

    @property
    def models_dir(self) -> str:
        return os.path.join(self.project_root, "backend", "models")


@dataclass
class MLConfig:
    """Machine learning / training hyperparameters."""
    hidden_dim:         int   = int(os.environ.get("ML_HIDDEN_DIM",   "64"))
    gnn_out_dim:        int   = int(os.environ.get("ML_GNN_OUT_DIM",  "32"))
    lr:                 float = float(os.environ.get("ML_LR",         "0.001"))
    gamma:              float = float(os.environ.get("ML_GAMMA",      "0.95"))
    epsilon_start:      float = float(os.environ.get("ML_EPS_START",  "1.0"))
    epsilon_min:        float = float(os.environ.get("ML_EPS_MIN",    "0.05"))
    epsilon_decay:      float = float(os.environ.get("ML_EPS_DECAY",  "0.995"))
    buffer_size:        int   = int(os.environ.get("ML_BUFFER",       "20000"))
    batch_size:         int   = int(os.environ.get("ML_BATCH",        "64"))
    target_update_freq: int   = int(os.environ.get("ML_TARGET_UPDATE","100"))
    num_actions:        int   = int(os.environ.get("ML_NUM_ACTIONS",  "4"))


@dataclass
class SimulationConfig:
    """Default simulation parameters."""
    default_duration:       int   = int(os.environ.get("SIM_DURATION",     "3600"))
    default_num_vehicles:   int   = int(os.environ.get("SIM_VEHICLES",     "200"))
    default_density_period: float = float(os.environ.get("SIM_DENSITY",    "2.0"))
    static_phase_duration:  int   = int(os.environ.get("SIM_PHASE_DUR",    "30"))
    metrics_save_interval:  int   = int(os.environ.get("SIM_METRICS_INT",  "60"))


# ----------------------------------------------------------------
# Global settings instances
# ----------------------------------------------------------------

sumo_settings       = SumoConfig()
server_settings     = ServerConfig()
path_settings       = PathConfig()
ml_settings         = MLConfig()
simulation_settings = SimulationConfig()


def get_settings() -> dict:
    """Return all settings as a flat dictionary (for API status endpoint)."""
    return {
        "sumo": {
            "home":      sumo_settings.sumo_home,
            "binary":    sumo_settings.binary,
            "port":      sumo_settings.traci_port,
        },
        "server": {
            "host":      server_settings.host,
            "port":      server_settings.port,
        },
        "ml": {
            "hidden_dim":    ml_settings.hidden_dim,
            "lr":            ml_settings.lr,
            "gamma":         ml_settings.gamma,
            "num_actions":   ml_settings.num_actions,
        },
        "simulation": {
            "default_duration": simulation_settings.default_duration,
            "default_vehicles": simulation_settings.default_num_vehicles,
        },
    }

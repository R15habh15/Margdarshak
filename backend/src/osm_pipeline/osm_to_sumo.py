"""
osm_to_sumo.py
Converts a downloaded .osm file into a SUMO-compatible road network (.net.xml)
using the netconvert tool bundled with SUMO.
"""

import os
import subprocess
import logging
from ..utils.sumo_utils import get_sumo_bin

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------
# Paths
# -------------------------------------------------------------------

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))

OSM_RAW_DIR = os.path.join(BASE_DIR, "data", "osm_raw")
SUMO_NETWORKS_DIR = os.path.join(BASE_DIR, "data", "sumo_networks")

os.makedirs(SUMO_NETWORKS_DIR, exist_ok=True)


# -------------------------------------------------------------------
# Resolve netconvert path
# -------------------------------------------------------------------

def _get_netconvert_path():
    """
    Resolve netconvert executable path reliably on Windows.
    """

    # Try SUMO_HOME environment variable
    sumo_home = os.environ.get("SUMO_HOME")

    if sumo_home:
        path = os.path.join(sumo_home, "bin", "netconvert.exe")
        if os.path.exists(path):
            return path

    # Default Windows installation path
    default_path = r"C:\Program Files (x86)\Eclipse\Sumo\bin\netconvert.exe"

    if os.path.exists(default_path):
        return default_path

    # Last fallback (if PATH contains SUMO)
    return "netconvert"


# -------------------------------------------------------------------
# Convert OSM → SUMO
# -------------------------------------------------------------------

def convert_osm_to_sumo(osm_filename: str) -> str:
    """
    Convert a .osm file to a SUMO .net.xml road network.
    """

    osm_path = os.path.join(OSM_RAW_DIR, osm_filename)

    if not os.path.exists(osm_path):
        raise FileNotFoundError(f"OSM file not found: {osm_path}")

    base_name = osm_filename.replace(".osm", "")
    net_path = os.path.join(SUMO_NETWORKS_DIR, f"{base_name}.net.xml")

    netconvert = _get_netconvert_path()

    logger.info(f"Using netconvert: {netconvert}")
    logger.info(f"Converting {osm_filename} to SUMO network...")

    print("OSM PATH:", osm_path)
    print("NET PATH:", net_path)
    print("NETCONVERT PATH:", netconvert)

    cmd = [
    netconvert,
    "--osm-files", osm_path,
    "--output-file", net_path,

    # Geometry cleanup
    "--geometry.remove",

    # Better intersection detection
    "--roundabouts.guess",
    "--ramps.guess",
    "--junctions.join",

    # 🚦 AUTO TRAFFIC LIGHT GENERATION
    "--tls.guess", "true",
    "--tls.join", "true",
    "--tls.discard-simple", "false",

    # Turn restrictions
    "--no-turnarounds", "true",

    # Keep only drivable roads
    "--keep-edges.by-vclass", "passenger",

    # Remove broken edges
    "--remove-edges.isolated",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=BASE_DIR
        )

        # Show SUMO output (useful for debugging)
        print(result.stdout)

        if result.returncode != 0:
            logger.error(f"netconvert error:\n{result.stderr}")
            raise RuntimeError(f"netconvert failed: {result.stderr}")

        logger.info(f"SUMO network saved to: {net_path}")

        return net_path

    except subprocess.TimeoutExpired:
        raise RuntimeError("netconvert timed out. Map region may be too large.")

    except FileNotFoundError:
        raise EnvironmentError(
            "netconvert executable not found. Check SUMO installation."
        )


# -------------------------------------------------------------------
# List networks
# -------------------------------------------------------------------

def list_sumo_networks() -> list:
    """Return list of all converted SUMO network files."""
    return [f for f in os.listdir(SUMO_NETWORKS_DIR) if f.endswith(".net.xml")]
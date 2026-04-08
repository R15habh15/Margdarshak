"""
traffic_generator.py
Generates random vehicle routes and a SUMO simulation config file
for a given SUMO road network.
"""

import os
import subprocess
import logging
import sys
from ..utils.sumo_utils import get_random_trips

logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))

SUMO_NETWORKS_DIR = os.path.join(BASE_DIR, "data", "sumo_networks")
ROUTES_DIR = os.path.join(BASE_DIR, "data", "routes")
CONFIGS_DIR = os.path.join(BASE_DIR, "data", "configs")

os.makedirs(ROUTES_DIR, exist_ok=True)
os.makedirs(CONFIGS_DIR, exist_ok=True)


def generate_routes(
    network_filename: str,
    num_vehicles: int = 4000,
    simulation_duration: int = 3600,
    vehicle_density_period: float = 0.9,   # ~4000 vehicles per hour (1 per 0.9s)
) -> dict:
    """
    Generate random vehicle routes for a SUMO simulation.
    """

    net_path = os.path.join(SUMO_NETWORKS_DIR, network_filename)

    if not os.path.exists(net_path):
        raise FileNotFoundError(f"SUMO network not found: {net_path}")

    base_name = network_filename.replace(".net.xml", "")

    route_path = os.path.join(ROUTES_DIR, f"{base_name}.rou.xml")
    config_path = os.path.join(CONFIGS_DIR, f"{base_name}.sumocfg")

    logger.info(f"Generating routes for: {network_filename}")

    random_trips_script = get_random_trips()

    print("NET PATH:", net_path)
    print("ROUTE PATH:", route_path)
    print("randomTrips PATH:", random_trips_script)

    trips_cmd = [
        sys.executable,               # portable python interpreter
        random_trips_script,
        "-n", net_path,
        "-r", route_path,
        "-e", str(simulation_duration),
        "-p", str(vehicle_density_period),
        "--validate",
        "--remove-loops",
        "--trip-attributes",
        'departLane="best" departSpeed="max"',
    ]

    try:
        result = subprocess.run(
            trips_cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=BASE_DIR
        )

        print(result.stdout)

        if result.returncode != 0:
            logger.warning(f"randomTrips warnings:\n{result.stderr}")

        logger.info(f"Routes saved to: {route_path}")

    except subprocess.TimeoutExpired:
        raise RuntimeError("Route generation timed out.")

    _write_sumo_config(config_path, net_path, route_path, simulation_duration)

    return {
        "network": net_path,
        "routes": route_path,
        "config": config_path,
        "duration": simulation_duration,
    }


def _write_sumo_config(config_path: str, net_path: str, route_path: str, duration: int):
    """Write a .sumocfg XML config file."""

    config_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<configuration xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xsi:noNamespaceSchemaLocation="http://sumo.dlr.de/xsd/sumoConfiguration.xsd">
    <input>
        <net-file value="{net_path}"/>
        <route-files value="{route_path}"/>
    </input>
    <time>
        <begin value="0"/>
        <end value="{duration}"/>
        <step-length value="1.0"/>
    </time>
    <processing>
        <ignore-route-errors value="true"/>
        <time-to-teleport value="60"/>
        <collision.action value="teleport"/>
        <collision.mingap-factor value="0"/>
        <time-to-teleport.highways value="30"/>
    </processing>
    <report>
        <verbose value="false"/>
        <no-step-log value="true"/>
        <no-warnings value="true"/>
    </report>
</configuration>
"""

    with open(config_path, "w") as f:
        f.write(config_xml)

    logger.info(f"SUMO config saved to: {config_path}")


def list_configs() -> list:
    """Return list of all generated .sumocfg files."""
    return [f for f in os.listdir(CONFIGS_DIR) if f.endswith(".sumocfg")]
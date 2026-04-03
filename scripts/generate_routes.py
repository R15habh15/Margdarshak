"""
generate_routes.py
CLI helper to generate random vehicle routes and a SUMO simulation config.

Usage:
    python scripts/generate_routes.py --network delhi.net.xml
    python scripts/generate_routes.py --network delhi.net.xml --vehicles 300 --duration 7200
    python scripts/generate_routes.py --list
"""

import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

from src.osm_pipeline.osm_to_sumo import list_sumo_networks
from src.osm_pipeline.traffic_generator import generate_routes, list_configs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s"
)

logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate vehicle routes for a SUMO network."
    )

    parser.add_argument(
        "--network",
        type=str,
        help="SUMO network filename (e.g. delhi.net.xml)"
    )

    parser.add_argument(
        "--vehicles",
        type=int,
        default=800,
        help="Approximate number of vehicles to generate (default: 800)"
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=3600,
        help="Simulation duration in seconds (default: 3600)"
    )

    parser.add_argument(
        "--period",
        type=float,
        default=None,
        help="Average seconds between vehicle insertions (auto-calculated if not provided)"
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List available networks and configs then exit"
    )

    return parser.parse_args()


def main():
    args = parse_args()

    # -------- LIST MODE --------
    if args.list:
        print("\n=== Available SUMO Networks ===")

        networks = list_sumo_networks()
        if not networks:
            print("  (none — run generate_sumo_network.py first)")
        else:
            for f in networks:
                print(f"  {f}")

        print("\n=== Generated Configs ===")

        configs = list_configs()
        if not configs:
            print("  (none yet)")
        else:
            for f in configs:
                print(f"  {f}")

        print()
        return

    # -------- VALIDATION --------

    if not args.network:
        print("Error: --network is required. Use --list to see available networks.")
        sys.exit(1)

    available = list_sumo_networks()

    if args.network not in available:
        print(f"Error: '{args.network}' not found.")
        print(f"Available networks: {available}")
        sys.exit(1)

    # -------- PERIOD CALCULATION --------

    if args.period is None:
        args.period = args.duration / max(args.vehicles, 1)

    logger.info(
        f"Generating routes for {args.network} | "
        f"vehicles~{args.vehicles} | duration={args.duration}s | period={args.period:.2f}s"
    )

    # -------- ROUTE GENERATION --------

    result = generate_routes(
        network_filename=args.network,
        num_vehicles=args.vehicles,
        simulation_duration=args.duration,
        vehicle_density_period=args.period,
    )

    # -------- OUTPUT --------

    print("\n✅ Done!")
    print(f"   Network  : {result['network']}")
    print(f"   Routes   : {result['routes']}")
    print(f"   Config   : {result['config']}")
    print(f"   Duration : {result['duration']}s")

    print("\nNext step:")
    print(f"  python scripts/start_simulation.py --config {os.path.basename(result['config'])}")
    print()


if __name__ == "__main__":
    main()
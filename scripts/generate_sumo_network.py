"""
generate_sumo_network.py
CLI helper to download an OSM map and convert it to a SUMO road network.

Usage:
    python scripts/generate_sumo_network.py --place "Connaught Place, Delhi, India"
    python scripts/generate_sumo_network.py --bbox 28.63 28.61 77.22 77.20 --name cp_delhi
    python scripts/generate_sumo_network.py --list
"""

import sys
import os
import argparse
import logging

# Ensure backend modules are importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

from src.osm_pipeline.osm_downloader import (
    download_osm_by_place,
    download_osm_by_bbox,
    list_downloaded_maps,
)

from src.osm_pipeline.osm_to_sumo import (
    convert_osm_to_sumo,
    list_sumo_networks,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s"
)

logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Download an OSM region and convert it into a SUMO road network."
    )

    source = parser.add_mutually_exclusive_group(required=True)

    source.add_argument(
        "--place",
        type=str,
        help="Place name, e.g. 'Connaught Place, Delhi, India'"
    )

    source.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        metavar=("NORTH", "SOUTH", "EAST", "WEST"),
        help="Bounding box: north south east west"
    )

    parser.add_argument(
        "--name",
        type=str,
        default="custom",
        help="Output label when using --bbox (default: custom)"
    )

    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip download if the .osm file already exists"
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="List downloaded maps and SUMO networks"
    )

    return parser.parse_args()


def main():
    args = parse_args()

    # List available maps
    if args.list:
        print("\n=== Downloaded OSM files ===")
        maps = list_downloaded_maps()

        if not maps:
            print("  (none)")
        else:
            for f in maps:
                print(f"  {f}")

        print("\n=== Converted SUMO Networks ===")
        nets = list_sumo_networks()

        if not nets:
            print("  (none)")
        else:
            for f in nets:
                print(f"  {f}")

        print()
        return

    osm_filename = None

    # -------- PLACE DOWNLOAD --------
    if args.place:

        safe_name = args.place.replace(",", "").replace(" ", "_").lower() + ".osm"

        if args.skip_download and safe_name in list_downloaded_maps():

            logger.info(f"Skipping download — {safe_name} already exists.")
            osm_filename = safe_name

        else:

            osm_path = download_osm_by_place(args.place)
            osm_filename = os.path.basename(osm_path)

    # -------- BBOX DOWNLOAD --------
    elif args.bbox:

        north, south, east, west = args.bbox

        safe_name = args.name.replace(" ", "_").lower() + ".osm"

        if args.skip_download and safe_name in list_downloaded_maps():

            logger.info(f"Skipping download — {safe_name} already exists.")
            osm_filename = safe_name

        else:

            osm_path = download_osm_by_bbox(
                north,
                south,
                east,
                west,
                name=args.name
            )

            osm_filename = os.path.basename(osm_path)

    # -------- CONVERT TO SUMO --------

    logger.info(f"Converting {osm_filename} to SUMO network...")

    net_path = convert_osm_to_sumo(osm_filename)

    # -------- SUCCESS MESSAGE --------

    print("\n✅ Done!")
    print(f"   OSM file : {osm_filename}")
    print(f"   SUMO net : {net_path}")

    print("\nNext step:")
    print(f"  python scripts/generate_routes.py --network {os.path.basename(net_path)}")
    print()


if __name__ == "__main__":
    main()
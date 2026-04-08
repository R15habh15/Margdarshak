"""
osm_downloader.py
Downloads a road network region from OpenStreetMap using osmnx
and saves it as a raw .osm file for further processing.
"""

import os
import osmnx as ox
import logging

logger = logging.getLogger(__name__)

# Improve reliability for large downloads
ox.settings.all_oneway = True
ox.settings.timeout = 300
ox.settings.use_cache = True

OSM_RAW_DIR = os.path.join(os.path.dirname(__file__), "../../../data/osm_raw")
os.makedirs(OSM_RAW_DIR, exist_ok=True)


def _fix_oneway_dtype(graph):
    """
    Fix OSMnx bug where 'oneway' values may appear as strings instead of bool.
    """
    for u, v, k, data in graph.edges(keys=True, data=True):
        if "oneway" in data:
            val = data["oneway"]

            if isinstance(val, str):
                data["oneway"] = val.lower() == "true"

            elif isinstance(val, list):
                data["oneway"] = bool(val[0])

            else:
                data["oneway"] = bool(val)

    return graph


def download_osm_by_place(place_name: str, dist: int = 2000) -> str:
    """
    Download road network for a named place.

    Strategy:
    1. Try graph_from_place()
    2. If it fails (no polygon or Overpass issue), fallback to graph_from_point()

    Args:
        place_name: e.g. "Karol Bagh, Delhi, India"
        dist: radius in meters if fallback is used

    Returns:
        Path to the saved .osm file
    """

    logger.info(f"Downloading OSM network for: {place_name}")

    try:
        # Attempt polygon download
        graph = ox.graph_from_place(place_name, network_type="drive", simplify=False)

    except Exception as e:
        logger.warning(
            f"graph_from_place failed for '{place_name}'. "
            f"Reason: {e}. Falling back to coordinate-based download."
        )

        try:
            # Convert place → coordinates
            point = ox.geocode(place_name)

            # Download roads around that point
            graph = ox.graph_from_point(
                point,
                dist=dist,
                network_type="drive",
                simplify=False
            )

        except Exception as e2:
            logger.error(f"Failed to download OSM for '{place_name}': {e2}")
            raise

    # Fix datatype issues
    graph = _fix_oneway_dtype(graph)

    # Normalize: collapse any run of spaces/commas/underscores into one underscore
    import re
    safe_name = re.sub(r'[,\s]+', '_', place_name).strip('_').lower()
    osm_path = os.path.join(OSM_RAW_DIR, f"{safe_name}.osm")


    ox.save_graph_xml(graph, filepath=osm_path)
    
    # Calculate center coordinates for camera positioning
    nodes = ox.graph_to_gdfs(graph, edges=False)
    center_y = float(nodes.y.mean())
    center_x = float(nodes.x.mean())

    logger.info(f"OSM file saved to: {osm_path} | Center: ({center_x}, {center_y})")
    
    return {
        "path": osm_path,
        "center": [center_x, center_y]
    }


def download_osm_by_bbox(north: float, south: float, east: float, west: float, name: str = "custom") -> str:
    """
    Download road network within a bounding box.

    Args:
        north, south, east, west: bounding box coordinates
        name: name of the saved map

    Returns:
        Path to the saved .osm file
    """

    logger.info(f"Downloading OSM network for bbox: N{north} S{south} E{east} W{west}")

    try:
        graph = ox.graph_from_bbox(
            north,
            south,
            east,
            west,
            network_type="drive",
            simplify=False
        )

        graph = _fix_oneway_dtype(graph)

        safe_name = name.replace(" ", "_").lower()
        osm_path = os.path.join(OSM_RAW_DIR, f"{safe_name}.osm")

        ox.save_graph_xml(graph, filepath=osm_path)
        
        # Calculate center
        nodes = ox.graph_to_gdfs(graph, edges=False)
        center_y = float(nodes.y.mean())
        center_x = float(nodes.x.mean())

        logger.info(f"OSM file saved to: {osm_path} | Center: ({center_x}, {center_y})")
        
        return {
            "path": osm_path,
            "center": [center_x, center_y]
        }

    except Exception as e:
        logger.error(f"Failed to download OSM for bbox: {e}")
        raise


def list_downloaded_maps() -> list:
    """Return list of all downloaded .osm files."""
    return [f for f in os.listdir(OSM_RAW_DIR) if f.endswith(".osm")]
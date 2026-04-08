"""
map_api.py
REST API endpoints for OSM map import and SUMO network conversion.
"""

import os
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from ..osm_pipeline.osm_downloader import (
    download_osm_by_place,
    download_osm_by_bbox,
    list_downloaded_maps,
)

from ..osm_pipeline.osm_to_sumo import (
    convert_osm_to_sumo,
    list_sumo_networks,
)

from ..osm_pipeline.traffic_generator import (
    generate_routes,
    list_configs,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ----------------------------------------------------------------
# Request Models
# ----------------------------------------------------------------

class DownloadByPlaceRequest(BaseModel):
    place_name: str


class DownloadByBboxRequest(BaseModel):
    north: float
    south: float
    east: float
    west: float
    name: Optional[str] = "custom"


class ConvertRequest(BaseModel):
    osm_filename: str


class GenerateRoutesRequest(BaseModel):
    network_filename: str
    num_vehicles: Optional[int] = 4000
    simulation_duration: Optional[int] = 3600
    vehicle_density_period: Optional[float] = 2.0


# ----------------------------------------------------------------
# MAP DOWNLOAD (FULL PIPELINE)
# ----------------------------------------------------------------

@router.post("/download/place")
async def download_map_by_place(req: DownloadByPlaceRequest):
    """
    Download map → Convert → Generate routes
    """

    try:
        # Step 1 — download OSM
        osm_res = download_osm_by_place(req.place_name)
        osm_path = osm_res["path"]
        center = osm_res["center"]

        # Extract filename
        osm_filename = os.path.basename(osm_path)

        # Step 2 — convert to SUMO
        net_path = convert_osm_to_sumo(osm_filename)
        net_filename = os.path.basename(net_path)

        # Step 3 — generate routes
        routes = generate_routes(net_filename)

        return {
            "status": "success",
            "place": req.place_name,
            "osm_file": osm_filename,
            "network_file": net_filename,
            "center": center,  # [lng, lat]
            "config": routes.get("config", ""),
            "config_file": os.path.basename(routes.get("config", "")),
            **{k: v for k, v in routes.items() if k != "config"},
        }


    except Exception as e:
        logger.error(f"Map download pipeline failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------------------------------------------
# DOWNLOAD BY BBOX
# ----------------------------------------------------------------

@router.post("/download/bbox")
async def download_map_by_bbox(req: DownloadByBboxRequest):

    try:
        osm_res = download_osm_by_bbox(
            req.north,
            req.south,
            req.east,
            req.west,
            req.name
        )
        osm_path = osm_res["path"]
        center = osm_res["center"]

        osm_filename = os.path.basename(osm_path)

        net_path = convert_osm_to_sumo(osm_filename)
        net_filename = os.path.basename(net_path)

        routes = generate_routes(net_filename)

        return {
            "status": "success",
            "osm_file": osm_filename,
            "network_file": net_filename,
            "center": center,
            **routes,
        }

    except Exception as e:
        logger.error(f"Bbox map download failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------------------------------------------
# CONVERT OSM → SUMO
# ----------------------------------------------------------------

@router.post("/convert")
async def convert_map(req: ConvertRequest):

    try:
        net_path = convert_osm_to_sumo(req.osm_filename)

        return {
            "status": "success",
            "net_path": net_path
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"Map conversion failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------------------------------------------
# ROUTE GENERATION
# ----------------------------------------------------------------

@router.post("/generate-routes")
async def generate_traffic_routes(req: GenerateRoutesRequest):

    try:
        result = generate_routes(
            network_filename=req.network_filename,
            num_vehicles=req.num_vehicles,
            simulation_duration=req.simulation_duration,
            vehicle_density_period=req.vehicle_density_period,
        )

        return {
            "status": "success",
            **result
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    except Exception as e:
        logger.error(f"Route generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------------------------------------------
# LIST MAPS
# ----------------------------------------------------------------

@router.get("/list")
async def list_maps():

    return {
        "osm_files": list_downloaded_maps(),
        "sumo_networks": list_sumo_networks(),
        "configs": list_configs(),
    }
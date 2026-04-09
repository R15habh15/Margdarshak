"""
scenario_api.py — Scenario Builder + Smart Emergency Preemption

Emergency Vehicle Green Wave (FIXED):
- Spawned vehicle uses an existing vehicle's full multi-edge route (not a 2-edge direct route)
- setSpeedMode(0) = respect NOTHING (full emergency override)
- Continuous preemption via tick_emergency_preemption() called from the WS stream loop
- Only signals within PREEMPT_RADIUS m AHEAD of the vehicle get green
- Crossing/opposing signals at the same junction get red
"""

import logging
import math
import random
import traci
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

logger = logging.getLogger(__name__)
router = APIRouter()

PREEMPT_RADIUS = 150.0   # meters ahead of emergency vehicle to green signals


def _get_env():
    from .simulation_api import _env
    return _env


# ── Scenario state ──────────────────────────────────────────────
_active_scenarios = {
    "rush_hour":            False,
    "road_closure":         False,
    "rain":                 False,
    "emergency_active":     False,
    "emergency_vehicle_id": None,
    "closed_edges":         [],
    "injected_vehicles":    [],
}


# ── Request Models ──────────────────────────────────────────────
class EmergencyRequest(BaseModel):
    origin_edge:      Optional[str] = None
    destination_edge: Optional[str] = None

class RushHourRequest(BaseModel):
    extra_vehicles: Optional[int] = 150

class RainRequest(BaseModel):
    speed_factor: Optional[float] = 0.6

class RoadClosureRequest(BaseModel):
    edge_id: Optional[str] = None


# ================================================================
# GREEN WAVE HELPERS
# ================================================================

def _geo_distance(x1, y1, x2, y2) -> float:
    """Euclidean distance in SUMO XY coords (metres)."""
    return math.sqrt((x1 - x2) ** 2 + (y1 - y2) ** 2)


def _get_greenest_phase(tl_id: str) -> int:
    """Return the phase index with the most 'G' characters."""
    try:
        programs = traci.trafficlight.getAllProgramLogics(tl_id)
        if not programs:
            return 0
        phases = programs[0].phases
        return max(range(len(phases)), key=lambda i: phases[i].state.upper().count("G"), default=0)
    except Exception:
        return 0


def _get_reddest_phase(tl_id: str) -> int:
    """Return the phase index with the most 'r' characters (crossing traffic gets red)."""
    try:
        programs = traci.trafficlight.getAllProgramLogics(tl_id)
        if not programs:
            return 0
        phases = programs[0].phases
        return max(range(len(phases)), key=lambda i: phases[i].state.lower().count("r"), default=0)
    except Exception:
        return 0


def tick_emergency_preemption():
    """
    Called EVERY simulation step from the WebSocket stream loop.
    Finds the active emergency vehicle, looks at TLs within PREEMPT_RADIUS
    of its position, and sets approach-side signals to GREEN, cross signals to RED.
    When the vehicle no longer exists, disables preemption.
    """
    ev_id = _active_scenarios.get("emergency_vehicle_id")
    if not ev_id:
        return

    # Check vehicle still exists
    try:
        active_vehicles = traci.vehicle.getIDList()
    except Exception:
        return

    if ev_id not in active_vehicles:
        # Vehicle finished its route — disable
        _active_scenarios["emergency_active"]     = False
        _active_scenarios["emergency_vehicle_id"] = None
        logger.info(f"Emergency vehicle {ev_id} finished route. Preemption disabled.")
        return

    try:
        # Get emergency vehicle's position and heading
        vx, vy = traci.vehicle.getPosition(ev_id)
        heading = traci.vehicle.getAngle(ev_id)   # 0 = North, 90 = East, etc.
        speed   = traci.vehicle.getSpeed(ev_id)

        # Keep its speed up — don't let SUMO slow it
        if speed < 12.0:
            traci.vehicle.setSpeed(ev_id, 14.0)   # ~50 km/h minimum

        # Get all junction positions
        tl_ids = traci.trafficlight.getIDList()
        for tl_id in tl_ids:
            try:
                junc_id = traci.trafficlight.getJunctionID(tl_id)
                jx, jy  = traci.junction.getPosition(junc_id)
            except Exception:
                continue

            dist = _geo_distance(vx, vy, jx, jy)

            if dist <= PREEMPT_RADIUS:
                # Check if junction is roughly AHEAD (within ±90° of heading)
                angle_to_junc = math.degrees(math.atan2(jx - vx, jy - vy)) % 360
                heading_norm  = heading % 360
                angle_diff    = abs(angle_to_junc - heading_norm)
                if angle_diff > 180:
                    angle_diff = 360 - angle_diff

                if angle_diff <= 90:
                    # Junction is AHEAD → force GREEN
                    green = _get_greenest_phase(tl_id)
                    traci.trafficlight.setPhase(tl_id, green)
                    traci.trafficlight.setPhaseDuration(tl_id, 30)
                else:
                    # Junction is BEHIND or BESIDE → force RED for crossing traffic
                    red = _get_reddest_phase(tl_id)
                    traci.trafficlight.setPhase(tl_id, red)
                    traci.trafficlight.setPhaseDuration(tl_id, 15)

    except Exception as e:
        logger.debug(f"Emergency preemption tick error: {e}")


# ================================================================
# 1. Spawn Emergency Vehicle
# ================================================================

@router.post("/emergency")
async def spawn_emergency_vehicle(req: EmergencyRequest):
    """Spawn an emergency vehicle that gets a continuous green wave ahead of it."""
    env = _get_env()
    if not env or not env.running:
        raise HTTPException(status_code=400, detail="Simulation is not running.")

    try:
        vehicle_ids = traci.vehicle.getIDList()
        if not vehicle_ids:
            raise HTTPException(status_code=400, detail="No vehicles in simulation yet.")

        ev_id    = f"emergency_{random.randint(1000, 9999)}"
        route_id = f"route_{ev_id}"

        # Borrow a complete multi-edge route from an existing vehicle
        template       = random.choice(vehicle_ids)
        existing_route = list(traci.vehicle.getRoute(template))

        if len(existing_route) < 2:
            # Grab any longer route
            for v in vehicle_ids:
                r = list(traci.vehicle.getRoute(v))
                if len(r) >= 2:
                    existing_route = r
                    break

        if len(existing_route) < 2:
            raise HTTPException(status_code=400, detail="Cannot find a multi-edge route for the emergency vehicle.")

        traci.route.add(route_id, existing_route)

        traci.vehicle.add(
            vehID       = ev_id,
            routeID     = route_id,
            typeID      = "DEFAULT_VEHTYPE",
            depart      = "now",
            departLane  = "best",
            departSpeed = "max",
        )

        # Red colour + full override (no safety constraints at all)
        traci.vehicle.setColor(ev_id, (255, 30, 30, 255))
        traci.vehicle.setSpeedMode(ev_id, 0)    # 0 = ignore ALL safety / traffic lights
        traci.vehicle.setLaneChangeMode(ev_id, 0)  # ignore lane-change rules
        traci.vehicle.setSpeed(ev_id, 14.0)      # ~50 km/h

        _active_scenarios["emergency_active"]     = True
        _active_scenarios["emergency_vehicle_id"] = ev_id

        logger.info(f"Emergency vehicle {ev_id} spawned | route length={len(existing_route)} edges")
        return {
            "status":     "emergency_spawned",
            "vehicle_id": ev_id,
            "route_edges": len(existing_route),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Emergency vehicle spawn failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ================================================================
# 2. Rush Hour Surge
# ================================================================

@router.post("/rush-hour")
async def activate_rush_hour(req: RushHourRequest):
    """Inject extra vehicles to simulate rush hour."""
    env = _get_env()
    if not env or not env.running:
        raise HTTPException(status_code=400, detail="Simulation is not running.")

    try:
        vehicle_ids = traci.vehicle.getIDList()
        if not vehicle_ids:
            raise HTTPException(status_code=400, detail="No vehicles to clone routes from.")

        injected = []
        count    = min(req.extra_vehicles, 100)

        for _ in range(count):
            template = random.choice(vehicle_ids)
            route    = list(traci.vehicle.getRoute(template))
            if not route:
                continue
            rid = f"rush_route_{random.randint(10000, 99999)}"
            vid = f"rush_{random.randint(10000, 99999)}"
            try:
                traci.route.add(rid, route)
                traci.vehicle.add(vehID=vid, routeID=rid, depart="now",
                                  departLane="random", departSpeed="random")
                injected.append(vid)
            except Exception:
                pass

        _active_scenarios["rush_hour"] = True
        _active_scenarios["injected_vehicles"].extend(injected)
        return {"status": "rush_hour_activated", "injected": len(injected)}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ================================================================
# 3. Road Closure
# ================================================================

@router.post("/road-closure")
async def activate_road_closure(req: RoadClosureRequest):
    """Block a road segment to near-zero speed."""
    env = _get_env()
    if not env or not env.running:
        raise HTTPException(status_code=400, detail="Simulation is not running.")

    try:
        edge_id = req.edge_id
        if not edge_id:
            vlist = traci.vehicle.getIDList()
            if not vlist:
                raise HTTPException(status_code=400, detail="No vehicles.")
            edge_id = traci.vehicle.getRoadID(random.choice(vlist))

        lanes = traci.edge.getLaneNumber(edge_id)
        for idx in range(lanes):
            try:
                traci.lane.setMaxSpeed(f"{edge_id}_{idx}", 0.5)
            except Exception:
                pass

        _active_scenarios["road_closure"] = True
        _active_scenarios["closed_edges"].append(edge_id)
        return {"status": "road_closure_activated", "edge_id": edge_id}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ================================================================
# 4. Rain
# ================================================================

@router.post("/rain")
async def activate_rain(req: RainRequest):
    """Reduce all vehicle max speeds by a factor."""
    env = _get_env()
    if not env or not env.running:
        raise HTTPException(status_code=400, detail="Simulation is not running.")

    try:
        factor = max(0.2, min(req.speed_factor, 1.0))
        vlist  = traci.vehicle.getIDList()
        for vid in vlist:
            try:
                traci.vehicle.setMaxSpeed(vid, traci.vehicle.getMaxSpeed(vid) * factor)
            except Exception:
                pass
        _active_scenarios["rain"] = True
        return {"status": "rain_activated", "speed_factor": factor, "vehicles_affected": len(vlist)}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ================================================================
# 5. Clear All
# ================================================================

@router.post("/clear")
async def clear_scenarios():
    """Restore normal simulation conditions."""
    env = _get_env()
    if not env or not env.running:
        raise HTTPException(status_code=400, detail="Simulation is not running.")

    try:
        for edge_id in _active_scenarios["closed_edges"]:
            try:
                lanes = traci.edge.getLaneNumber(edge_id)
                for idx in range(lanes):
                    traci.lane.setMaxSpeed(f"{edge_id}_{idx}", 13.89)
            except Exception:
                pass

        try:
            for vid in traci.vehicle.getIDList():
                traci.vehicle.setMaxSpeed(vid, -1)
        except Exception:
            pass

    except Exception as e:
        logger.warning(f"TraCI error during scenario clear: {e}")

    # Always reset the state dictionaries!
    _active_scenarios.update({
        "rush_hour": False, "road_closure": False, "rain": False,
        "emergency_active": False, "emergency_vehicle_id": None,
        "closed_edges": [], "injected_vehicles": [],
    })
    return {"status": "scenarios_cleared"}


# ================================================================
# 6. Status
# ================================================================

@router.get("/status")
async def scenario_status():
    return {
        "rush_hour":     _active_scenarios["rush_hour"],
        "road_closure":  _active_scenarios["road_closure"],
        "rain":          _active_scenarios["rain"],
        "emergency":     _active_scenarios["emergency_active"],
        "emergency_veh": _active_scenarios["emergency_vehicle_id"],
        "closed_edges":  _active_scenarios["closed_edges"],
    }

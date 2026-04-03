"""
simulation_api.py
REST + WebSocket API endpoints for controlling the simulation.

REST Endpoints:
  POST /api/simulation/start      — start simulation
  POST /api/simulation/stop       — stop simulation
  POST /api/simulation/reset      — reset simulation
  POST /api/simulation/set-mode   — switch static / AI mode
  GET  /api/simulation/status     — current simulation status

WebSocket:
  WS  /api/simulation/stream      — real-time state stream (1 step/sec)
"""

import asyncio
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import os

from ..simulation.traffic_env import TrafficEnv
from ..simulation.signal_controller import SignalMode
from ..sensing.state_vector import build_network_state
from ..brain.drl_agent import DRLAgent
from ..brain.backpressure import backpressure_actions

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
CONFIG_DIR = os.path.join(BASE_DIR, "data", "configs")

logger = logging.getLogger(__name__)
router = APIRouter()

# Single shared simulation instance (one simulation at a time)
_env: Optional[TrafficEnv] = None
_agent: Optional[DRLAgent] = None


# ----------------------------------------------------------------
# Request Models
# ----------------------------------------------------------------

class StartRequest(BaseModel):
    config_path: str
    mode: Optional[str]       = "static"   # "static" | "ai" | "backpressure"
    use_gui: Optional[bool]   = False
    port: Optional[int]       = 8813

class SetModeRequest(BaseModel):
    mode: str                              # "static" | "ai" | "backpressure"


# ----------------------------------------------------------------
# REST Endpoints
# ----------------------------------------------------------------

@router.post("/start")
async def start_simulation(req: StartRequest):
    """Start the simulation with the given config and mode."""
    global _env

    if _env and _env.running:
        raise HTTPException(status_code=409, detail="Simulation already running. Call /stop first.")

    mode = SignalMode.AI if req.mode == "ai" else SignalMode.STATIC

    try:
        config_file = os.path.join(CONFIG_DIR, req.config_path)

        if not os.path.exists(config_file):
            raise HTTPException(
                status_code=500,
                detail=f"SUMO config not found: {config_file}"
            )

        _env = TrafficEnv(config_path=config_file, mode=mode, use_gui=req.use_gui)
        _env.start(port=req.port)
        return {
            "status": "started",
            "mode": req.mode,
            "config": req.config_path,
        }
    except Exception as e:
        logger.error(f"Failed to start simulation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_simulation():
    """Stop the running simulation."""
    global _env
    if not _env or not _env.running:
        raise HTTPException(status_code=400, detail="No simulation is currently running.")
    _env.stop()
    return {"status": "stopped"}


@router.post("/reset")
async def reset_simulation():
    """Reset and restart the simulation from the beginning."""
    global _env
    if not _env:
        raise HTTPException(status_code=400, detail="No simulation to reset.")
    try:
        _env.reset()
        return {"status": "reset"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/set-mode")
async def set_mode(req: SetModeRequest):
    """Switch signal control mode mid-simulation."""
    global _env
    if not _env or not _env.running:
        raise HTTPException(status_code=400, detail="Simulation is not running.")

    if req.mode not in ("static", "ai", "backpressure"):
        raise HTTPException(status_code=422, detail="mode must be static | ai | backpressure")

    mode = SignalMode.AI if req.mode == "ai" else SignalMode.STATIC
    _env.set_mode(mode)
    return {"status": "mode_updated", "mode": req.mode}


@router.get("/status")
async def get_status():
    """Return current simulation status and step info."""
    if not _env:
        return {"running": False, "step": 0, "mode": None}
    return {
        "running":  _env.running,
        "step":     _env.bridge.get_step(),
        "sim_time": _env.bridge.get_simulation_time(),
        "mode":     _env.mode,
        "done":     _env.is_done() if _env.running else False,
    }


# ----------------------------------------------------------------
# WebSocket: real-time simulation stream
# ----------------------------------------------------------------

@router.websocket("/stream")
async def simulation_stream(websocket: WebSocket):
    """
    WebSocket endpoint that streams live simulation state.

    Each message is a JSON snapshot of the current step state.
    Client can send "stop" to terminate the stream.
    """
    global _env, _agent

    await websocket.accept()
    logger.info("WebSocket client connected to simulation stream.")

    if not _env or not _env.running:
        await websocket.send_json({"error": "No simulation running."})
        await websocket.close()
        return

    try:
        while _env.running and not _env.is_done():
            ai_actions = None

            # Determine actions based on current mode
            if _env.mode == SignalMode.AI and _agent:
                state_matrix, raw_features, tl_order = build_network_state(_env.bridge)
                ai_actions = _agent.select_actions(state_matrix, greedy=True)

            elif _env.mode == SignalMode.AI:
                # Fallback to backpressure if no agent loaded
                ai_actions = backpressure_actions(_env.bridge)

            # Step simulation
            state = _env.step(ai_actions=ai_actions)

            # Send compact state snapshot to frontend
            payload = {
                "step":             state["step"],
                "sim_time":         state["sim_time"],
                "active_vehicles":  state["active_vehicles"],
                "departed":         state["departed"],
                "arrived":          state["arrived"],
                "mode":             state["mode"],
                "traffic_lights":   {
                    tl_id: {
                        "phase":         data["phase"],
                        "total_vehicles": sum(l["vehicle_count"] for l in data["lanes"].values()),
                        "total_queue":    sum(l["queue_length"]  for l in data["lanes"].values()),
                        "total_wait":     sum(l["waiting_time"]  for l in data["lanes"].values()),
                    }
                    for tl_id, data in state["traffic_lights"].items()
                },
            }
            await websocket.send_json(payload)

            # Yield control so FastAPI can handle other requests
            await asyncio.sleep(0.05)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as e:
        logger.error(f"WebSocket stream error: {e}")
        await websocket.send_json({"error": str(e)})
    finally:
        await websocket.close()
        logger.info("WebSocket connection closed.")

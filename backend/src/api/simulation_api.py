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
import time
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
_sim_speed: int = 5   # steps per WebSocket frame (1=realtime, 5=5x, 10=10x, etc.)


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

class SetSpeedRequest(BaseModel):
    speed: int = 5                         # steps per frame: 1, 2, 5, 10, 20


# ----------------------------------------------------------------
# REST Endpoints
# ----------------------------------------------------------------

@router.post("/start")
async def start_simulation(req: StartRequest):
    """Start the simulation with the given config and mode."""
    global _env

    if _env and _env.running:
        raise HTTPException(status_code=409, detail="Simulation already running. Call /stop first.")

    if req.mode == 'ai':
        mode = SignalMode.AI
    elif req.mode == 'backpressure':
        mode = SignalMode.STATIC   # SUMO mode; backpressure is handled at action level
    else:
        mode = SignalMode.STATIC

    try:
        config_file = os.path.join(CONFIG_DIR, req.config_path)

        if not os.path.exists(config_file):
            raise HTTPException(
                status_code=500,
                detail=f"SUMO config not found: {config_file}"
            )

        _env = TrafficEnv(config_path=config_file, mode=mode, use_gui=req.use_gui)
        _env.start(port=req.port)
        _env._requested_mode = req.mode   # preserve backpressure/ai/static string


        # ── Auto-load AI Agent ──
        if req.mode == "ai":
            try:
                from ..brain.model_manager import ModelManager
                from ..brain.drl_agent import DRLAgent
                from ..utils.graph_builder import load_sumo_network, build_tl_graph
                
                logger.info("Initializing AI Agent for optimization...")
                tl_ids = _env.bridge.get_traffic_light_ids()
                net_file = os.path.join(SUMO_NETWORKS_DIR, req.config_path.replace(".sumocfg", ".net.xml"))
                net = load_sumo_network(net_file)
                _, edge_index, _ = build_tl_graph(net, tl_ids)

                global _agent
                _agent = DRLAgent(tl_ids=tl_ids, edge_index=edge_index)
                
                mm = ModelManager()
                if mm.load_inference_model(_agent, "rl_policy.pt"):
                    logger.info("AI Model 'rl_policy.pt' loaded successfully.")
                else:
                    logger.warning("No trained AI model found. Simulation will use default heuristics.")
            except Exception as e:
                logger.error(f"AI Auto-load error: {e}")

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

    mode = SignalMode.AI if req.mode == 'ai' else SignalMode.STATIC
    _env.set_mode(mode)
    _env._requested_mode = req.mode   # track mode string for WS stream
    _env.mode = req.mode
    return {"status": "mode_updated", "mode": req.mode}


@router.post("/set-speed")
async def set_speed(req: SetSpeedRequest):
    """Set simulation speed multiplier (steps per WebSocket frame)."""
    global _sim_speed
    _sim_speed = max(1, min(req.speed, 50))  # clamp 1-50
    logger.info(f"Simulation speed set to {_sim_speed}x")
    return {"status": "speed_updated", "speed": _sim_speed}


@router.get("/status")
async def get_status():
    """Return current simulation status and step info."""
    if not _env:
        return {"running": False, "step": 0, "mode": None, "speed": _sim_speed}
    return {
        "running":  _env.running,
        "step":     _env.bridge.get_step(),
        "sim_time": _env.bridge.get_simulation_time(),
        "mode":     _env.mode,
        "speed":    _sim_speed,
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
    global _env, _agent, _sim_speed

    await websocket.accept()
    logger.info("WebSocket client connected to simulation stream.")

    if not _env or not _env.running:
        await websocket.send_json({"error": "No simulation running."})
        await websocket.close()
        return

    try:
        from ..api.scenario_api import tick_emergency_preemption, _active_scenarios as _scen

        while _env.running and not _env.is_done():
            loop_start = time.time()

            # ── Run N simulation steps per frame (speed multiplier) ──
            steps_this_frame = _sim_speed
            state = None

            for _ in range(steps_this_frame):
                if not _env.running or _env.is_done():
                    break

                ai_actions = None

                # Emergency preemption
                if _scen.get("emergency_active"):
                    tick_emergency_preemption()

                # Resolve mode
                raw_mode = str(_env.mode).lower()
                mode_str = raw_mode.split('.')[-1] if '.' in raw_mode else raw_mode
                req_mode = getattr(_env, '_requested_mode', mode_str)

                if req_mode == 'ai':
                    if _agent:
                        state_matrix, _, _ = build_network_state(_env.bridge)
                        ai_actions = _agent.select_actions(state_matrix, greedy=True)
                    else:
                        ai_actions = backpressure_actions(_env.bridge)
                elif req_mode == 'backpressure':
                    ai_actions = backpressure_actions(_env.bridge)

                state = _env.step(ai_actions=ai_actions)

            if state is None:
                break

            # Build TL payload (only for the last step in the batch)
            tl_payload = {}
            for tl_id, data in state.get("traffic_lights", {}).items():
                lng = data.get("lng") or 0
                lat = data.get("lat") or 0
                if not lng or not lat:
                    continue
                tl_payload[tl_id] = {
                    "phase":          data.get("phase", 0),
                    "lng":            lng,
                    "lat":            lat,
                    "total_vehicles": sum(l.get("vehicle_count", 0) for l in data.get("lanes", {}).values()),
                    "total_queue":    sum(l.get("queue_length",  0) for l in data.get("lanes", {}).values()),
                    "total_wait":     sum(l.get("waiting_time",  0) for l in data.get("lanes", {}).values()),
                }

            raw_mode = str(_env.mode).lower()
            mode_str = raw_mode.split('.')[-1] if '.' in raw_mode else raw_mode
            req_mode = getattr(_env, '_requested_mode', mode_str)

            payload = {
                "step":            state.get("step", 0),
                "sim_time":        state.get("sim_time", 0.0),
                "active_vehicles": state.get("active_vehicles", 0),
                "departed":        state.get("departed", 0),
                "arrived":         state.get("arrived", 0),
                "avg_speed_kmh":   state.get("avg_speed_kmh", 0),
                "total_wait":      state.get("total_wait", 0),
                "avg_wait":        state.get("avg_wait", 0),
                "total_queue":     state.get("total_queue", 0),
                "mode":            req_mode,
                "speed":           _sim_speed,
                "vehicles":        _env.bridge.get_all_vehicle_positions(),
                "traffic_lights":  tl_payload,
            }

            loop_elapsed = time.time() - loop_start
            wait_time = max(0.001, 0.0333 - loop_elapsed)  # Target ~30 FPS output

            await websocket.send_json(payload)
            await asyncio.sleep(wait_time)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as e:
        logger.error(f"WebSocket stream error: {e}")
        await websocket.send_json({"error": str(e)})
    finally:
        await websocket.close()
        logger.info("WebSocket connection closed.")

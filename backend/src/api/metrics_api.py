"""
metrics_api.py
REST API endpoints for fetching traffic performance metrics.

Endpoints:
  GET  /api/metrics/current     — live metrics from current simulation step
  GET  /api/metrics/summary     — aggregated metrics for the full run
  GET  /api/metrics/history     — time-series history (for charts)
  GET  /api/metrics/comparison  — side-by-side static vs AI comparison
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)
router = APIRouter()

# Shared reference to simulation environment (set by simulation_api)
# We import lazily to avoid circular imports
def _get_env():
    from .simulation_api import _env
    return _env


# Store separate metric summaries for static / backpressure / ai runs
_comparison_store: dict = {
    "static":      None,
    "ai":          None,
    "backpressure": None,
}


# ----------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------

@router.get("/current")
async def get_current_metrics():
    """
    Return live metrics from the most recent simulation step.
    """
    env = _get_env()
    if not env or not env.running:
        raise HTTPException(status_code=400, detail="No simulation is running.")

    state = env.get_current_state()
    if not state:
        return {"status": "no_data_yet"}

    return {
        "step":             state.get("step", 0),
        "sim_time":         state.get("sim_time", 0),
        "mode":             state.get("mode", "unknown"),
        "active_vehicles":  state.get("active_vehicles", 0),
        "total_queue":      state.get("total_queue", 0),
        "total_wait":       state.get("total_wait", 0),
        "avg_wait":         state.get("avg_wait", 0),
        "avg_speed_ms":     round(state.get("avg_speed_kmh", 0) / 3.6, 3),
        "avg_speed_kmh":    state.get("avg_speed_kmh", 0),
        "departed":         state.get("departed", 0),
        "arrived":          state.get("arrived", 0),
    }


@router.get("/summary")
async def get_metrics_summary():
    """
    Return aggregated performance summary for the current simulation run.
    """
    env = _get_env()
    if not env:
        raise HTTPException(status_code=400, detail="No simulation instance found.")
    return env.get_metrics_summary()


@router.get("/history")
async def get_metrics_history():
    """
    Return the time-series metrics history for chart visualization.
    """
    env = _get_env()
    if not env:
        raise HTTPException(status_code=400, detail="No simulation instance found.")
    summary = env.get_metrics_summary()
    return {
        "mode":    summary["mode"],
        "history": summary["history"],
    }


@router.post("/comparison/save")
async def save_comparison_snapshot():
    """
    Save current run metrics to the comparison store.
    Call this after finishing a static run and after an AI run
    to populate the comparison view.
    """
    env = _get_env()
    if not env:
        raise HTTPException(status_code=400, detail="No simulation instance found.")

    summary = env.get_metrics_summary()
    mode    = str(summary["mode"])

    mode = str(summary["mode"]).lower()

    if mode in _comparison_store:
        _comparison_store[mode] = summary
        return {"status": "saved", "mode": mode}
    elif mode == "signalmode.ai":
        _comparison_store["ai"] = summary
        return {"status": "saved", "mode": "ai"}
    elif mode == "signalmode.static":
        _comparison_store["static"] = summary
        return {"status": "saved", "mode": "static"}
    else:
        # Best-effort: store under closest match
        _comparison_store["static"] = summary
        return {"status": "saved", "mode": mode}


@router.get("/comparison")
async def get_comparison():
    """
    Return side-by-side metrics comparing static vs AI signal control.

    Includes calculated improvement percentages.
    """
    static = _comparison_store.get("static")
    bp     = _comparison_store.get("backpressure")
    ai     = _comparison_store.get("ai")

    def pct_change(base, new_val):
        if not base or base == 0:
            return 0.0
        return round((new_val - base) / base * 100, 2)

    def mode_block(m):
        if not m:
            return None
        return {
            "total_waiting_time": m.get("total_waiting_time", 0),
            "total_arrived":      m.get("total_arrived", 0),
            "total_departed":     m.get("total_departed", 0),
            "total_steps":        m.get("total_steps", 0),
        }

    s_block  = mode_block(static)
    bp_block = mode_block(bp)
    ai_block = mode_block(ai)

    improvement = {}
    if static and ai:
        improvement = {
            "waiting_time_change_pct":  pct_change(static["total_waiting_time"], ai["total_waiting_time"]),
            "throughput_change_pct":    pct_change(static["total_arrived"],      ai["total_arrived"]),
            "waiting_reduced":          ai["total_waiting_time"] < static["total_waiting_time"],
            "throughput_increased":     ai["total_arrived"] > static["total_arrived"],
        }

    ready = bool(static or bp or ai)

    return {
        "ready":        ready,
        "static":       s_block,
        "backpressure": bp_block,
        "ai":           ai_block,
        "improvement":  improvement,
        "message": None if ready else "Run simulations and save each mode.",
    }

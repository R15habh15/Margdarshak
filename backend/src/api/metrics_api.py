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


# Store separate metric summaries for static vs AI runs
_comparison_store: dict = {
    "static": None,
    "ai":     None,
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

    tl_data = state.get("traffic_lights", {})

    total_vehicles  = state.get("active_vehicles", 0)
    total_queue     = sum(
        sum(l["queue_length"]  for l in tl["lanes"].values())
        for tl in tl_data.values()
    )
    total_wait      = sum(
        sum(l["waiting_time"]  for l in tl["lanes"].values())
        for tl in tl_data.values()
    )
    avg_speed       = 0.0
    lane_count      = 0
    for tl in tl_data.values():
        for lane in tl["lanes"].values():
            if lane["vehicle_count"] > 0:
                avg_speed  += lane["mean_speed"]
                lane_count += 1
    if lane_count > 0:
        avg_speed /= lane_count

    return {
        "step":             state.get("step", 0),
        "sim_time":         state.get("sim_time", 0),
        "mode":             state.get("mode", "unknown"),
        "active_vehicles":  total_vehicles,
        "total_queue":      total_queue,
        "total_wait":       round(total_wait, 2),
        "avg_speed_ms":     round(avg_speed, 3),
        "avg_speed_kmh":    round(avg_speed * 3.6, 2),
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

    if mode in _comparison_store:
        _comparison_store[mode] = summary
        return {"status": "saved", "mode": mode}
    else:
        raise HTTPException(status_code=422, detail=f"Unknown mode: {mode}")


@router.get("/comparison")
async def get_comparison():
    """
    Return side-by-side metrics comparing static vs AI signal control.

    Includes calculated improvement percentages.
    """
    static = _comparison_store.get("static")
    ai     = _comparison_store.get("ai")

    if not static or not ai:
        return {
            "ready":  False,
            "static": static,
            "ai":     ai,
            "message": "Run both static and AI simulations then call /comparison/save for each.",
        }

    def pct_change(base, new):
        if base == 0:
            return 0.0
        return round((new - base) / base * 100, 2)

    wait_improvement    = pct_change(static["total_waiting_time"], ai["total_waiting_time"])
    arrived_improvement = pct_change(static["total_arrived"],      ai["total_arrived"])

    return {
        "ready":  True,
        "static": {
            "total_waiting_time": static["total_waiting_time"],
            "total_arrived":      static["total_arrived"],
            "total_departed":     static["total_departed"],
            "total_steps":        static["total_steps"],
        },
        "ai": {
            "total_waiting_time": ai["total_waiting_time"],
            "total_arrived":      ai["total_arrived"],
            "total_departed":     ai["total_departed"],
            "total_steps":        ai["total_steps"],
        },
        "improvement": {
            "waiting_time_change_pct":  wait_improvement,
            "throughput_change_pct":    arrived_improvement,
            "waiting_reduced":          wait_improvement < 0,
            "throughput_increased":     arrived_improvement > 0,
        },
    }

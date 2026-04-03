"""
state_vector.py
Converts raw junction traffic features into normalised state vectors
for input into the GNN and RL agent.

State vector layout (8 features per junction):
  [0]  norm_vehicle_count    — vehicles present at junction
  [1]  norm_queue_length     — halted vehicles
  [2]  norm_waiting_time     — cumulative waiting time
  [3]  norm_avg_speed        — mean vehicle speed
  [4]  norm_lane_density     — vehicles / lane
  [5]  norm_wait_per_lane    — waiting time / lane
  [6]  phase_sin             — cyclic sine encoding of current phase
  [7]  phase_cos             — cyclic cosine encoding of current phase

Multi-city / unified-graph usage
---------------------------------
Pass `tl_order`  = unified_tl_ids   (full node list, length N)
     `node_mask` = city_masks[city] (bool array, length N)

Nodes absent in the current city keep zero features. The mask is
returned and used by DRLAgent to exclude those nodes from the loss.
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Feature dimension per junction node
STATE_DIM = 8

# Normalisation upper bounds
MAX_VEHICLES = 50.0
MAX_QUEUE    = 30.0
MAX_WAITING  = 300.0   # seconds
MAX_SPEED    = 20.0    # m/s  (~72 km/h)
MAX_PRESSURE = 40.0


def _safe_feature_row(
    bridge,
    tl_id: str,
) -> Tuple[np.ndarray, Dict]:
    """
    Extract and normalise an 8-dim feature vector for one junction.
    Returns (feature_row, raw_dict).
    """

    try:
        lanes      = bridge.get_controlled_lanes(tl_id)
        lane_count = max(len(lanes), 1)

        total_queue   = 0.0
        total_wait    = 0.0
        total_speed   = 0.0
        vehicle_count = 0

        for lane in lanes:
            total_queue   += bridge.get_lane_queue_length(lane)
            total_wait    += bridge.get_lane_waiting_time(lane)
            total_speed   += bridge.get_lane_mean_speed(lane)
            vehicle_count += bridge.get_lane_vehicle_count(lane)

        avg_speed = total_speed / lane_count

        raw = {
            "total_queue_length" : total_queue,
            "total_waiting_time" : total_wait,
            "avg_speed"          : avg_speed,
            "vehicle_count"      : vehicle_count,
        }

        row = np.array([
            min(vehicle_count              / MAX_VEHICLES, 1.0),
            min(total_queue                / MAX_QUEUE,    1.0),
            min(total_wait                 / MAX_WAITING,  1.0),
            min(avg_speed                  / MAX_SPEED,    1.0),
            min(vehicle_count / lane_count / MAX_VEHICLES, 1.0),   # lane density
            min(total_wait    / lane_count / MAX_WAITING,  1.0),   # wait per lane
            0.0,   # phase_sin — filled below
            0.0,   # phase_cos
        ], dtype=np.float32)

        # Cyclic phase encoding
        try:
            phase     = bridge.get_tl_phase(tl_id)
            n_phases  = bridge.get_tl_phase_count(tl_id)
            angle     = (2 * np.pi * phase) / max(n_phases, 1)
            row[6]    = float(np.sin(angle))
            row[7]    = float(np.cos(angle))
        except Exception:
            pass   # leave 0,0 if phase query fails

        return row, raw

    except Exception as e:
        logger.debug(f"Feature extraction failed for {tl_id}: {e}")
        return np.zeros(STATE_DIM, dtype=np.float32), {
            "total_queue_length" : 0.0,
            "total_waiting_time" : 0.0,
            "avg_speed"          : 0.0,
            "vehicle_count"      : 0,
        }


def build_network_state(
    bridge,
    tl_order: Optional[List[str]]  = None,
    node_mask: Optional[np.ndarray] = None,
) -> Tuple[np.ndarray, Dict, Dict]:
    """
    Build the normalised state matrix for all nodes in `tl_order`.

    Parameters
    ----------
    bridge     : TraCIBridge connected to the current simulation
    tl_order   : ordered list of TL IDs (unified_tl_ids for multi-city)
    node_mask  : bool array (len = len(tl_order))
                 True  → node exists in current city, query bridge
                 False → node absent, keep zero features
                 If None, all nodes are treated as active.

    Returns
    -------
    state_matrix : np.ndarray  (N, STATE_DIM)  — zero-padded where masked
    raw_features : dict  {tl_id -> feature dict}  — only active nodes
    tl_index_map : dict  {tl_id -> row index}
    """

    tl_ids = tl_order if tl_order is not None else bridge.get_traffic_light_ids()
    N      = len(tl_ids)

    state_matrix = np.zeros((N, STATE_DIM), dtype=np.float32)
    raw_features : Dict = {}
    tl_index_map = {tid: i for i, tid in enumerate(tl_ids)}

    # Which nodes to actually query
    if node_mask is not None:
        active_indices = np.where(node_mask)[0]
    else:
        active_indices = np.arange(N)

    for idx in active_indices:
        tl_id = tl_ids[idx]
        row, raw = _safe_feature_row(bridge, tl_id)
        state_matrix[idx] = row
        raw_features[tl_id] = raw

    return state_matrix, raw_features, tl_index_map


def get_state_dim() -> int:
    return STATE_DIM


def describe_state_vector() -> List[str]:
    return [
        "norm_vehicle_count",
        "norm_queue_length",
        "norm_waiting_time",
        "norm_avg_speed",
        "norm_lane_density",
        "norm_wait_per_lane",
        "phase_sin",
        "phase_cos",
    ]
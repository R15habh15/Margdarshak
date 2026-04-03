"""
traffic_features.py
Extracts raw traffic features from SUMO simulation via TraCIBridge.

For each traffic light junction this module collects:
  - Per-lane: vehicle count, mean speed, waiting time, occupancy, queue length
  - Junction-level aggregates: total queue, avg speed, traffic pressure

This is the perception layer — reads the environment state each simulation step.
"""

import logging
import traci
from typing import Dict
from ..simulation.traci_bridge import TraCIBridge

logger = logging.getLogger(__name__)


def extract_lane_features(bridge: TraCIBridge, lane_id: str) -> dict:
    """
    Extract all traffic features for a single lane.

    Args:
        bridge: Active TraCIBridge instance
        lane_id: SUMO lane identifier

    Returns:
        Dict of raw lane-level features
    """
    return {
        "lane_id": lane_id,
        "vehicle_count":  bridge.get_lane_vehicle_count(lane_id),
        "mean_speed":     round(bridge.get_lane_mean_speed(lane_id), 3),
        "waiting_time":   round(bridge.get_lane_waiting_time(lane_id), 3),
        "occupancy":      round(bridge.get_lane_occupancy(lane_id), 3),
        "queue_length":   bridge.get_lane_queue_length(lane_id),
    }


def extract_junction_features(bridge: TraCIBridge, tl_id: str) -> dict:
    """
    Extract aggregated traffic features for a single junction.

    Collects per-lane data for all incoming lanes controlled by
    this traffic light and computes junction-level statistics.

    Args:
        bridge: Active TraCIBridge instance
        tl_id:  Traffic light / junction ID

    Returns:
        Dict with per-lane features and junction-level aggregates
    """
    controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
    unique_lanes = list(set(controlled_lanes))

    lane_features = {}
    total_vehicles  = 0
    total_waiting   = 0.0
    total_queue     = 0
    speed_sum       = 0.0
    speed_count     = 0

    for lane_id in unique_lanes:
        feat = extract_lane_features(bridge, lane_id)
        lane_features[lane_id] = feat

        total_vehicles += feat["vehicle_count"]
        total_waiting  += feat["waiting_time"]
        total_queue    += feat["queue_length"]

        if feat["vehicle_count"] > 0:
            speed_sum   += feat["mean_speed"]
            speed_count += 1

    avg_speed        = round(speed_sum / speed_count, 3) if speed_count > 0 else 0.0
    outgoing_count   = _count_outgoing_vehicles(tl_id)
    pressure         = total_vehicles - outgoing_count   # backpressure signal

    return {
        "tl_id":              tl_id,
        "current_phase":      bridge.get_tl_phase(tl_id),
        "lane_count":         len(unique_lanes),
        "total_vehicles":     total_vehicles,
        "total_waiting_time": round(total_waiting, 3),
        "total_queue_length": total_queue,
        "avg_speed":          avg_speed,
        "pressure":           pressure,
        "lanes":              lane_features,
    }


def extract_all_junctions(bridge: TraCIBridge) -> Dict[str, dict]:
    """
    Extract features for every traffic light junction in the network.

    Returns:
        Dict mapping tl_id -> junction feature dict
    """
    all_features = {}
    for tl_id in bridge.get_traffic_light_ids():
        try:
            all_features[tl_id] = extract_junction_features(bridge, tl_id)
        except Exception as e:
            logger.warning(f"Failed to extract features for junction {tl_id}: {e}")
    return all_features


def _count_outgoing_vehicles(tl_id: str) -> int:
    """
    Count vehicles on outgoing lanes from a junction.
    Used for traffic pressure computation.
    """
    try:
        links = traci.trafficlight.getControlledLinks(tl_id)
        outgoing_lanes = set()
        for link_group in links:
            for link in link_group:
                # link tuple: (incoming_lane, outgoing_lane, via_lane)
                if len(link) >= 2 and link[1]:
                    outgoing_lanes.add(link[1])
        return sum(traci.lane.getLastStepVehicleNumber(l) for l in outgoing_lanes)
    except Exception:
        return 0

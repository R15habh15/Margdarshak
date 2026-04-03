"""
backpressure.py
Implements the Backpressure Traffic Control Algorithm.

Backpressure is a classical, provably throughput-optimal control policy.
It computes a "pressure" score for each signal phase at each junction
based on the difference in vehicle queue lengths on incoming vs outgoing lanes.

The phase with the highest pressure is activated — ensuring the most
congested incoming roads are cleared first.

This module serves two roles:
  1. A standalone baseline controller (no ML required)
  2. A supplementary pressure signal fed into the RL reward function
"""

import logging
import traci
import numpy as np
from typing import Dict, List, Tuple
from ..simulation.traci_bridge import TraCIBridge

logger = logging.getLogger(__name__)


def compute_lane_pressure(
    incoming_lane: str,
    outgoing_lane: str,
) -> float:
    """
    Compute pressure for a single lane pair.

    Pressure = queue(incoming) - queue(outgoing)

    Args:
        incoming_lane: Lane approaching the junction
        outgoing_lane: Lane leaving the junction

    Returns:
        Pressure value (positive = congested incoming)
    """
    try:
        q_in  = traci.lane.getLastStepHaltingNumber(incoming_lane)
        q_out = traci.lane.getLastStepHaltingNumber(outgoing_lane)
        return float(q_in - q_out)
    except Exception:
        return 0.0


def compute_phase_pressure(tl_id: str, phase_index: int) -> float:
    """
    Compute aggregate pressure for a specific signal phase.

    A phase controls a set of lane-to-lane movements (links).
    We sum the pressure of all green movements in that phase.

    Args:
        tl_id:       Traffic light ID
        phase_index: Phase index to evaluate

    Returns:
        Total pressure score for this phase
    """
    try:
        programs = traci.trafficlight.getAllProgramLogics(tl_id)
        if not programs:
            return 0.0

        program = programs[0]
        if phase_index >= len(program.phases):
            return 0.0

        phase_state  = program.phases[phase_index].state   # e.g. "GGrr"
        links        = traci.trafficlight.getControlledLinks(tl_id)
        total_pressure = 0.0

        for link_idx, signal_char in enumerate(phase_state):
            if signal_char.upper() != "G":
                continue   # Only count green movements
            if link_idx >= len(links):
                continue

            link_group = links[link_idx]
            for link in link_group:
                if len(link) >= 2 and link[0] and link[1]:
                    total_pressure += compute_lane_pressure(link[0], link[1])

        return total_pressure

    except Exception as e:
        logger.warning(f"Error computing phase pressure for {tl_id} phase {phase_index}: {e}")
        return 0.0


def select_best_phase(tl_id: str, num_phases: int) -> int:
    """
    Select the signal phase with the highest backpressure score.

    Args:
        tl_id:      Traffic light ID
        num_phases: Total number of available phases

    Returns:
        Index of the best phase
    """
    pressures = [
        compute_phase_pressure(tl_id, p)
        for p in range(num_phases)
    ]
    best_phase = int(np.argmax(pressures))
    logger.debug(f"TL {tl_id} pressures={pressures} -> phase {best_phase}")
    return best_phase


def compute_network_pressure(bridge: TraCIBridge) -> Dict[str, float]:
    """
    Compute backpressure scores for all junctions.

    Returns:
        Dict mapping tl_id -> pressure score
    """
    pressure_map = {}
    for tl_id in bridge.get_traffic_light_ids():
        num_phases = bridge.get_tl_phase_count(tl_id)
        current    = bridge.get_tl_phase(tl_id)
        pressure   = compute_phase_pressure(tl_id, current)
        pressure_map[tl_id] = pressure
    return pressure_map


def backpressure_actions(bridge: TraCIBridge) -> Dict[str, int]:
    """
    Compute backpressure-optimal phase actions for all junctions.

    Suitable for use as a standalone controller or as a reward
    baseline comparison for the RL agent.

    Returns:
        Dict mapping tl_id -> recommended phase index
    """
    actions = {}
    for tl_id in bridge.get_traffic_light_ids():
        num_phases    = bridge.get_tl_phase_count(tl_id)
        actions[tl_id] = select_best_phase(tl_id, num_phases)
    return actions

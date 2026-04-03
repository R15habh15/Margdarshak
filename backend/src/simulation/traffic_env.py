"""
traffic_env.py
Central simulation orchestrator for Margadarshak.
"""

import logging
import time
from typing import Dict, Optional, List
from dataclasses import dataclass, field

from .traci_bridge import TraCIBridge
from .signal_controller import SignalController, SignalMode

logger = logging.getLogger(__name__)


@dataclass
class SimulationMetrics:
    total_waiting_time: float = 0.0
    total_vehicles_departed: int = 0
    total_vehicles_arrived: int = 0
    total_steps: int = 0
    metrics_history: List[dict] = field(default_factory=list)


class TrafficEnv:

    def __init__(self, config_path: str, mode: SignalMode = SignalMode.STATIC, use_gui: bool = False):

        self.config_path = config_path
        self.mode = mode
        self.use_gui = use_gui

        self.bridge = TraCIBridge()
        self.controller: Optional[SignalController] = None
        self.metrics = SimulationMetrics()

        self.running = False
        self.current_state: Dict = {}

    # ------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------

    def start(self, port: int = 8813) -> bool:

        logger.info(f"Starting TrafficEnv | mode={self.mode} | config={self.config_path}")

        self.bridge.start(self.config_path, port=port, use_gui=self.use_gui)

        self.controller = SignalController(self.bridge, mode=self.mode)
        self.controller.initialize()

        self.metrics = SimulationMetrics()
        self.running = True

        logger.info("TrafficEnv started.")
        return True

    def stop(self):

        self.running = False
        self.bridge.stop()
        logger.info("TrafficEnv stopped.")

    def reset(self, port: int = 8813):

        self.stop()
        time.sleep(1)
        self.start(port=port)

    # ------------------------------------------------------------
    # Simulation Step
    # ------------------------------------------------------------

    def step(self, ai_actions: Optional[Dict[str, int]] = None) -> dict:

        if not self.running:
            raise RuntimeError("Simulation is not running. Call start() first.")

        # Apply controller logic
        self.controller.step(ai_actions=ai_actions)

        # Advance SUMO
        self.bridge.step()

        # Extract new state
        state = self._extract_state()

        self.current_state = state

        # Update metrics
        self._update_metrics(state)

        return state

    # ------------------------------------------------------------
    # State Extraction
    # ------------------------------------------------------------

    def _extract_state(self) -> dict:

        import traci

        sim_time = self.bridge.get_simulation_time()
        step = self.bridge.get_step()

        active_vehicles = self.bridge.get_active_vehicle_count()
        departed = self.bridge.get_departed_vehicles()
        arrived = self.bridge.get_arrived_vehicles()

        tl_states = {}

        tl_ids = self.bridge.get_traffic_light_ids()

        for tl_id in tl_ids:

            try:

                controlled_lanes = traci.trafficlight.getControlledLanes(tl_id)
                unique_lanes = list(set(controlled_lanes))

                lane_data = {}

                for lane_id in unique_lanes:

                    lane_data[lane_id] = {
                        "vehicle_count": self.bridge.get_lane_vehicle_count(lane_id),
                        "mean_speed": round(self.bridge.get_lane_mean_speed(lane_id), 2),
                        "waiting_time": round(self.bridge.get_lane_waiting_time(lane_id), 2),
                        "occupancy": round(self.bridge.get_lane_occupancy(lane_id), 2),
                        "queue_length": self.bridge.get_lane_queue_length(lane_id),
                    }

                # safer phase retrieval
                try:
                    phase = self.bridge.get_tl_phase(tl_id)
                except Exception:
                    phase = 0

                # Get coordinates for the traffic light
                junction_id = traci.trafficlight.getJunctionID(tl_id)
                jx, jy = traci.junction.getPosition(junction_id)
                jlon, jlat = self.bridge.convert_geo(jx, jy)

                tl_states[tl_id] = {
                    "phase": phase,
                    "lanes": lane_data,
                    "lng": jlon,
                    "lat": jlat,
                }

            except Exception as e:

                logger.warning(f"Skipping TL {tl_id}: {e}")

        return {
            "sim_time": sim_time,
            "step": step,
            "active_vehicles": active_vehicles,
            "departed": departed,
            "arrived": arrived,
            "traffic_lights": tl_states,
            "signal_states": self.controller.get_all_states(),
            "mode": self.mode,
        }

    # ------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------

    def _update_metrics(self, state: dict):

        self.metrics.total_steps += 1

        self.metrics.total_vehicles_departed += state["departed"]
        self.metrics.total_vehicles_arrived += state["arrived"]

        waiting_sum = 0.0

        for tl_data in state["traffic_lights"].values():
            for lane_data in tl_data["lanes"].values():
                waiting_sum += lane_data["waiting_time"]

        self.metrics.total_waiting_time += waiting_sum

        if self.metrics.total_steps % 60 == 0:

            self.metrics.metrics_history.append({
                "step": self.metrics.total_steps,
                "sim_time": state["sim_time"],
                "active_vehicles": state["active_vehicles"],
                "total_waiting_time": self.metrics.total_waiting_time,
                "departed": self.metrics.total_vehicles_departed,
                "arrived": self.metrics.total_vehicles_arrived,
            })

    # ------------------------------------------------------------
    # Public Metrics API
    # ------------------------------------------------------------

    def get_metrics_summary(self) -> dict:

        steps = max(self.metrics.total_steps, 1)

        return {
            "mode": self.mode,
            "total_steps": self.metrics.total_steps,
            "total_departed": self.metrics.total_vehicles_departed,
            "total_arrived": self.metrics.total_vehicles_arrived,
            "total_waiting_time": round(self.metrics.total_waiting_time, 2),
            "avg_waiting_time_per_step": round(self.metrics.total_waiting_time / steps, 4),
            "history": self.metrics.metrics_history,
        }

    def get_current_state(self) -> dict:
        return self.current_state

    def is_done(self) -> bool:
        return self.bridge.is_simulation_finished()

    def set_mode(self, mode: SignalMode):

        self.mode = mode

        if self.controller:
            self.controller.set_mode(mode)
"""
traci_bridge.py
Manages the connection between Python and SUMO simulator via TraCI.

Responsibilities:
- Start and stop SUMO simulation
- Step the simulation forward
- Provide a clean interface for querying/controlling SUMO
"""

import os
import traci
import logging
from typing import Optional

logger = logging.getLogger(__name__)

SUMO_BINARY = os.environ.get("SUMO_BINARY", "sumo")


class TraCIBridge:
    """Manages a single SUMO simulation session via TraCI."""

    def __init__(self):
        self.connected: bool = False
        self.step_count: int = 0
        self.config_path: Optional[str] = None

    def start(self, config_path: str, port: int = 8813, use_gui: bool = False) -> bool:
        """
        Launch SUMO and connect via TraCI.

        Args:
            config_path: Path to the .sumocfg file
            port: TraCI server port
            use_gui: Open SUMO graphical window if True

        Returns:
            True if connection was successful
        """
        if self.connected:
            logger.warning("TraCI already connected. Call stop() first.")
            return False

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"SUMO config not found: {config_path}")

        self.config_path = config_path
        binary = "sumo-gui" if use_gui else SUMO_BINARY

        sumo_cmd = [
            binary,
            "-c", config_path,
            "--no-step-log", "true",
            "--waiting-time-memory", "1000",
            "--no-warnings", "true",
        ]

        try:
            traci.start(sumo_cmd, port=port)
            self.connected = True
            self.step_count = 0
            logger.info(f"TraCI connected on port {port} | config: {config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to start TraCI: {e}")
            raise

    def step(self) -> int:
        """Advance simulation by one time step. Returns current step count."""
        if not self.connected:
            raise RuntimeError("TraCI is not connected. Call start() first.")
        traci.simulationStep()
        self.step_count += 1
        return self.step_count

    def stop(self):
        """Close TraCI connection and terminate SUMO."""
        if self.connected:
            try:
                traci.close()
                logger.info("TraCI connection closed.")
            except Exception as e:
                logger.warning(f"Error closing TraCI: {e}")
            finally:
                self.connected = False
                self.step_count = 0

    # ------------------------------------------------------------------
    # Simulation Info
    # ------------------------------------------------------------------

    def is_connected(self) -> bool:
        return self.connected

    def get_step(self) -> int:
        return self.step_count

    def get_simulation_time(self) -> float:
        if not self.connected:
            return 0.0
        return traci.simulation.getTime()

    def get_departed_vehicles(self) -> int:
        return traci.simulation.getDepartedNumber()

    def get_arrived_vehicles(self) -> int:
        return traci.simulation.getArrivedNumber()

    def get_active_vehicles(self) -> list:
        return traci.vehicle.getIDList()

    def get_active_vehicle_count(self) -> int:
        return traci.vehicle.getIDCount()

    def convert_geo(self, x: float, y: float) -> tuple:
        """Convert internal XY to (Lon, Lat)."""
        if not self.connected:
            return (0.0, 0.0)
        return traci.simulation.convertGeo(x, y)

    def get_all_vehicle_positions(self) -> list:
        if not self.connected:
            return []
        positions = []
        for veh_id in traci.vehicle.getIDList():
            x, y = traci.vehicle.getPosition(veh_id)
            lon, lat = traci.simulation.convertGeo(x, y)
            speed = traci.vehicle.getSpeed(veh_id) * 3.6
            angle = traci.vehicle.getAngle(veh_id)
            positions.append({
                "id": veh_id, 
                "lng": lon, 
                "lat": lat,
                "speed": round(speed, 2),
                "angle": round(angle, 2)
            })
        return positions

    def is_simulation_finished(self) -> bool:
        return (
            traci.simulation.getMinExpectedNumber() == 0
            and self.get_active_vehicle_count() == 0
        )

    # ------------------------------------------------------------------
    # Traffic Light Control
    # ------------------------------------------------------------------

    def get_traffic_light_ids(self) -> list:
        return traci.trafficlight.getIDList()

    def get_tl_phase(self, tl_id: str) -> int:
        return traci.trafficlight.getPhase(tl_id)

    def set_tl_phase(self, tl_id: str, phase: int):
        traci.trafficlight.setPhase(tl_id, phase)

    def get_tl_program(self, tl_id: str):
        return traci.trafficlight.getAllProgramLogics(tl_id)

    def get_tl_phase_count(self, tl_id: str) -> int:
        programs = self.get_tl_program(tl_id)
        if programs:
            return len(programs[0].phases)
        return 0

    def set_tl_phase_duration(self, tl_id: str, duration: int):
        traci.trafficlight.setPhaseDuration(tl_id, duration)

    # ------------------------------------------------------------------
    # Lane Queries
    # ------------------------------------------------------------------

    def get_lane_vehicle_count(self, lane_id: str) -> int:
        return traci.lane.getLastStepVehicleNumber(lane_id)

    def get_lane_mean_speed(self, lane_id: str) -> float:
        return traci.lane.getLastStepMeanSpeed(lane_id)

    def get_lane_waiting_time(self, lane_id: str) -> float:
        return traci.lane.getWaitingTime(lane_id)

    def get_lane_occupancy(self, lane_id: str) -> float:
        return traci.lane.getLastStepOccupancy(lane_id)

    def get_lane_queue_length(self, lane_id: str) -> float:
        return traci.lane.getLastStepHaltingNumber(lane_id)
    def get_controlled_lanes(self, tl_id: str):
        """
        Return unique lanes controlled by a traffic light.
        """

        import traci

        try:
            lanes = traci.trafficlight.getControlledLanes(tl_id)

            # remove duplicates
            return list(set(lanes))

        except Exception:
            return []
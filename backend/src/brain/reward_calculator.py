"""
reward_calculator.py
Computes the RL reward signal from raw junction traffic features.

Reward Components:
  1. Waiting Time Penalty   — punish cumulative vehicle waiting
  2. Queue Length Penalty   — punish lane congestion
  3. Throughput Reward      — reward vehicles completing trips
  4. Speed Reward           — reward high average network speed
  5. Pressure Penalty       — penalize high backpressure differentials
  6. Phase Change Penalty   — small cost for unnecessary signal switches

All components are normalised by active node count so that rewards
are comparable across cities of different sizes.
"""

import logging
import numpy as np
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Reward component weights
W_WAIT       = -0.0005   # per second of cumulative waiting
W_QUEUE      = -0.002   # per halted vehicle in queue
W_THROUGHPUT =  0.2   # per vehicle that arrived this step
W_SPEED      =  0.01   # per m/s of average network speed
W_PRESSURE   = -0.001   # per unit of traffic pressure
W_SWITCH     = -0.001   # per phase switch (discourages instability)


class RewardCalculator:
    """
    Stateful reward calculator — tracks previous step state for
    delta-based components (throughput, phase switches).

    One instance should be created per worker and reset() called
    at the start of each episode / env restart.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self._prev_arrived               = 0
        self._prev_phases: Dict[str, int] = {}

        self.weights = {
            "wait"       : W_WAIT,
            "queue"      : W_QUEUE,
            "throughput" : W_THROUGHPUT,
            "speed"      : W_SPEED,
            "pressure"   : W_PRESSURE,
            "switch"     : W_SWITCH,
        }
        if weights:
            self.weights.update(weights)

    def reset(self):
        """Reset between episodes."""
        self._prev_arrived = 0
        self._prev_phases  = {}

    def compute(
        self,
        raw_features   : Dict[str, dict],
        arrived_total  : int,
        current_phases : Dict[str, int],
    ) -> Dict[str, float]:
        """
        Compute reward for the current step.

        Parameters
        ----------
        raw_features   : {tl_id -> feature dict} from build_network_state
                         Keys used: total_waiting_time, total_queue_length,
                                    avg_speed, pressure (optional)
        arrived_total  : cumulative vehicles arrived network-wide (from bridge)
        current_phases : {tl_id -> current phase index}

        Returns
        -------
        dict with keys: wait, queue, throughput, speed, pressure, switch, total
        """

        n_active = max(len(raw_features), 1)

        # 1. Waiting time penalty
        total_wait = sum(f["total_waiting_time"] for f in raw_features.values())
        r_wait     = self.weights["wait"] * total_wait

        # 2. Queue length penalty
        total_queue = sum(f["total_queue_length"] for f in raw_features.values())
        r_queue     = self.weights["queue"] * total_queue

        # 3. Throughput reward (delta arrivals since last step)
        delta_arrived  = max(arrived_total - self._prev_arrived, 0)
        r_throughput = self.weights["throughput"] * np.tanh(delta_arrived)
        self._prev_arrived = arrived_total

        # 4. Speed reward
        speeds    = [f["avg_speed"] for f in raw_features.values() if f.get("avg_speed", 0) > 0]
        avg_speed = float(np.mean(speeds)) if speeds else 0.0
        r_speed   = self.weights["speed"] * avg_speed

        # 5. Pressure penalty
        total_pressure = sum(
            abs(f.get("pressure", 0.0)) for f in raw_features.values()
        )
        r_pressure = self.weights["pressure"] * total_pressure

        # 6. Phase switch penalty
        switches = sum(
            1 for tl_id, phase in current_phases.items()
            if self._prev_phases.get(tl_id) != phase
        )
        r_switch          = self.weights["switch"] * switches
        self._prev_phases = dict(current_phases)

        total = r_wait + r_queue + r_throughput + r_speed + r_pressure + r_switch

        # Normalise by active node count — keeps reward scale consistent
        # across cities with different numbers of junctions
        total = total / n_active
        total = max(min(total, 1.0), -1.0)

        components = {
            "wait"       : round(r_wait,       5),
            "queue"      : round(r_queue,      5),
            "throughput" : round(r_throughput, 5),
            "speed"      : round(r_speed,      5),
            "pressure"   : round(r_pressure,   5),
            "switch"     : round(r_switch,     5),
            "total"      : round(total,        5),
        }

        logger.debug(f"Reward: {components}")
        return components

    def scalar(
        self,
        raw_features   : Dict[str, dict],
        arrived_total  : int,
        current_phases : Dict[str, int],
    ) -> float:
        """Returns the total scalar reward only."""
        return self.compute(raw_features, arrived_total, current_phases)["total"]
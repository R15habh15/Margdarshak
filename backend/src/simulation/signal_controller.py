"""
signal_controller.py
Manages traffic signal phase control for all intersections.
"""

import logging
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional
from .traci_bridge import TraCIBridge

logger = logging.getLogger(__name__)


class SignalMode(str, Enum):
    STATIC = "static"
    AI = "ai"


@dataclass
class SignalState:
    tl_id: str
    current_phase: int = 0
    phase_timer: int = 0
    phase_duration: int = 30
    total_phases: int = 1
    mode: SignalMode = SignalMode.STATIC


class SignalController:

    DEFAULT_PHASE_DURATION = 30
    MIN_PHASE_DURATION = 5
    MAX_PHASE_DURATION = 90

    def __init__(self, bridge: TraCIBridge, mode: SignalMode = SignalMode.STATIC):

        self.bridge = bridge
        self.mode = mode
        self.signals: Dict[str, SignalState] = {}
        self.last_action = {}
        self.last_switch_step = {}
        self.min_green_time = 8  # ✅ prevents rapid switching
        self.current_step = 0

    # -------------------------------------------------------------
    # Initialization
    # -------------------------------------------------------------

    def initialize(self):

        tl_ids = self.bridge.get_traffic_light_ids()

        logger.info(f"Initializing {len(tl_ids)} traffic lights in {self.mode} mode.")

        for tl_id in tl_ids:

            total_phases = self.bridge.get_tl_phase_count(tl_id)

            # Skip invalid traffic lights
            if total_phases <= 1:
                logger.debug(f"Skipping TL {tl_id} (only {total_phases} phase)")
                continue

            current_phase = self.bridge.get_tl_phase(tl_id)

            self.signals[tl_id] = SignalState(
                tl_id=tl_id,
                current_phase=current_phase,
                phase_timer=0,
                phase_duration=self.DEFAULT_PHASE_DURATION,
                total_phases=total_phases,
                mode=self.mode,
            )

        logger.info(f"Controlling {len(self.signals)} valid traffic lights.")

    # -------------------------------------------------------------
    # Mode Control
    # -------------------------------------------------------------

    def set_mode(self, mode: SignalMode):

        self.mode = mode

        for sig in self.signals.values():
            sig.mode = mode

        logger.info(f"Signal mode switched to: {mode}")

    # -------------------------------------------------------------
    # Simulation Step
    # -------------------------------------------------------------

    def step(self, ai_actions: Optional[Dict[str, int]] = None):

        for tl_id, state in self.signals.items():

            if self.mode == SignalMode.STATIC:
                self._step_static(state)

            elif self.mode == SignalMode.AI:
                action = ai_actions.get(tl_id) if ai_actions else None
                self._step_ai(state, action)

    # -------------------------------------------------------------
    # Static Mode
    # -------------------------------------------------------------

    def _step_static(self, state: SignalState):

        state.phase_timer += 1

        if state.phase_timer >= state.phase_duration:

            next_phase = (state.current_phase + 1) % state.total_phases

            self._apply_phase(state, next_phase)

            state.phase_timer = 0

    # -------------------------------------------------------------
    # AI Mode
    # -------------------------------------------------------------

    def _step_ai(self, state: SignalState, action: Optional[int]):

        self.current_step += 1

        tl_id = state.tl_id

        if action is None:
            state.phase_timer += 1
            return

        phase = action % state.total_phases

        # ✅ First-time initialization
        if tl_id not in self.last_action:
            self.last_action[tl_id] = state.current_phase
            self.last_switch_step[tl_id] = self.current_step

        # ✅ Prevent rapid switching (CRITICAL FIX)
        if phase != self.last_action[tl_id]:

            if self.current_step - self.last_switch_step[tl_id] < self.min_green_time:
                phase = self.last_action[tl_id]  # ❌ ignore fast switching
            else:
                self.last_switch_step[tl_id] = self.current_step
                self.last_action[tl_id] = phase

        # ✅ Apply phase only if changed
        if phase != state.current_phase:
            self._apply_phase(state, phase)
            state.phase_timer = 0
        else:
            state.phase_timer += 1

    # -------------------------------------------------------------
    # Phase Application
    # -------------------------------------------------------------

    def _apply_phase(self, state: SignalState, phase: int):

        try:

            self.bridge.set_tl_phase(state.tl_id, phase)

            state.current_phase = phase

        except Exception as e:

            logger.warning(f"Failed to set phase for {state.tl_id}: {e}")

    # -------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------

    def force_phase(self, tl_id: str, phase: int, duration: Optional[int] = None):

        if tl_id not in self.signals:
            raise ValueError(f"Unknown traffic light: {tl_id}")

        state = self.signals[tl_id]

        phase = phase % state.total_phases

        self._apply_phase(state, phase)

        if duration:

            clamped = max(self.MIN_PHASE_DURATION, min(duration, self.MAX_PHASE_DURATION))

            self.bridge.set_tl_phase_duration(tl_id, clamped)

    def get_all_states(self) -> Dict[str, dict]:

        return {
            tl_id: {
                "phase": state.current_phase,
                "timer": state.phase_timer,
                "duration": state.phase_duration,
                "total_phases": state.total_phases,
                "mode": state.mode,
            }
            for tl_id, state in self.signals.items()
        }

    def get_signal_ids(self):

        return list(self.signals.keys())
    
    def worker_process(config_path, agent, steps, queue, port):

        from src.simulation.traffic_env import TrafficEnv
        from src.sensing.state_vector import build_network_state

        env = TrafficEnv(config_path=config_path, mode="ai")

        env.start(port=port)

        # ❌ Skip invalid maps
        if len(env.bridge.get_traffic_light_ids()) == 0:
            env.stop()
            return

        for _ in range(steps):

            state_matrix, raw, _ = build_network_state(env.bridge, tl_order=agent.tl_ids)

            # ✅ Skip mismatched graph sizes
            if state_matrix.shape[0] != len(agent.tl_ids):
                continue

            actions = agent.select_actions(state_matrix)

            env.step(actions)

            next_state_matrix, raw_next, _ = build_network_state(env.bridge, tl_order=agent.tl_ids)

            if next_state_matrix.shape[0] != len(agent.tl_ids):
                continue

            reward = agent.compute_reward(raw_next)

            queue.put((state_matrix, actions, reward, next_state_matrix, False))

        env.stop()
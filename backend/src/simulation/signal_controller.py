"""
signal_controller.py
Manages traffic signal phase control for all intersections.

Key anti-deadlock features:
  - Detects green vs yellow/all-red phases and handles them differently
  - Adaptive green duration based on queue pressure
  - Deadlock detection via stagnant queue monitoring
  - Forced phase rotation to break gridlock
"""

import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Optional, List
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
    # Phase classification: True = green (vehicles move), False = yellow/all-red
    green_phases: List[int] = field(default_factory=list)
    # Deadlock tracking
    stagnant_steps: int = 0
    last_queue_snapshot: int = 0
    force_override_timer: int = 0
    target_phase: Optional[int] = None


class SignalController:

    DEFAULT_GREEN_DURATION = 40   # fixed seconds for all green phases
    YELLOW_DURATION = 5           # realistic transition for yellow/all-red
    MIN_PHASE_DURATION = 5
    MAX_PHASE_DURATION = 60
    DEADLOCK_THRESHOLD = 40       # steps of zero movement → deadlock
    DEADLOCK_FORCE_DURATION = 20  # increased forced green to fully flush gridlock

    def __init__(self, bridge: TraCIBridge, mode: SignalMode = SignalMode.STATIC):

        self.bridge = bridge
        self.mode = mode
        self.signals: Dict[str, SignalState] = {}
        self.last_action = {}
        self.last_switch_step = {}
        self.min_green_time = 15  # increased to prevent rapid switching and improve flow
        self.current_step = 0

    # -------------------------------------------------------------
    # Initialization
    # -------------------------------------------------------------

    def initialize(self):

        import traci

        tl_ids = self.bridge.get_traffic_light_ids()

        logger.info(f"Initializing {len(tl_ids)} traffic lights in {self.mode} mode.")

        for tl_id in tl_ids:

            total_phases = self.bridge.get_tl_phase_count(tl_id)

            # Skip invalid traffic lights
            if total_phases <= 1:
                logger.debug(f"Skipping TL {tl_id} (only {total_phases} phase)")
                continue

            current_phase = self.bridge.get_tl_phase(tl_id)

            # Classify which phases are "green" (have 'G' or 'g') vs transitional
            green_phases = []
            try:
                programs = traci.trafficlight.getAllProgramLogics(tl_id)
                if programs:
                    for i, phase in enumerate(programs[0].phases):
                        state_str = phase.state.upper()
                        if 'G' in state_str:
                            green_phases.append(i)
            except Exception:
                # Fallback: treat all even-indexed phases as green
                green_phases = list(range(0, total_phases, 2))

            if not green_phases:
                green_phases = list(range(total_phases))

            self.signals[tl_id] = SignalState(
                tl_id=tl_id,
                current_phase=current_phase,
                phase_timer=0,
                phase_duration=self.DEFAULT_GREEN_DURATION,
                total_phases=total_phases,
                mode=self.mode,
                green_phases=green_phases,
            )

            logger.debug(f"TL {tl_id}: {total_phases} phases, green={green_phases}")

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

        self.current_step += 1

        for tl_id, state in self.signals.items():

            if self.mode == SignalMode.STATIC:
                self._step_static(state)

            elif self.mode == SignalMode.AI:
                # ── Deadlock detection (runs only in AI mode) ──
                self._check_deadlock(state)
                action = ai_actions.get(tl_id) if ai_actions else None
                self._step_ai(state, action)

    # -------------------------------------------------------------
    # Deadlock Detection & Recovery
    # -------------------------------------------------------------

    def _check_deadlock(self, state: SignalState):
        """Monitor for gridlock and force phase rotation to break it."""
        try:
            controlled_lanes = self.bridge.get_controlled_lanes(state.tl_id)
            total_queue = sum(
                self.bridge.get_lane_queue_length(lane)
                for lane in controlled_lanes
            )

            # If queue is high and hasn't changed, increment stagnation counter
            if total_queue > 3 and total_queue == state.last_queue_snapshot:
                state.stagnant_steps += 1
            else:
                state.stagnant_steps = 0

            state.last_queue_snapshot = total_queue

            # Deadlock detected → force advance to next green phase
            if state.stagnant_steps >= self.DEADLOCK_THRESHOLD:
                logger.warning(
                    f"Deadlock detected at TL {state.tl_id} "
                    f"(queue={total_queue}, stagnant for {state.stagnant_steps} steps). "
                    f"Forcing phase rotation."
                )
                next_green = self._next_green_phase(state)
                self._apply_phase(state, next_green)
                state.phase_timer = 0
                state.phase_duration = self.DEADLOCK_FORCE_DURATION
                state.stagnant_steps = 0
                state.force_override_timer = self.DEADLOCK_FORCE_DURATION

        except Exception as e:
            logger.debug(f"Deadlock check error for {state.tl_id}: {e}")

    # -------------------------------------------------------------
    # Static Mode (phase-aware)
    # -------------------------------------------------------------

    def _step_static(self, state: SignalState):

        state.phase_timer += 1

        is_green = state.current_phase in state.green_phases

        # Green phases: dwell for the fixed configured duration
        # Yellow/all-red transitions: pass through quickly
        duration = self.DEFAULT_GREEN_DURATION if is_green else self.YELLOW_DURATION

        if state.phase_timer >= duration:
            next_phase = (state.current_phase + 1) % state.total_phases
            self._apply_phase(state, next_phase)
            state.phase_timer = 0
            state.phase_duration = self.DEFAULT_GREEN_DURATION

    # -------------------------------------------------------------
    # AI Mode
    # -------------------------------------------------------------

    def _step_ai(self, state: SignalState, action: Optional[int]):

        tl_id = state.tl_id

        if state.force_override_timer > 0:
            state.force_override_timer -= 1
            state.phase_timer += 1
            return

        if action is None:
            state.phase_timer += 1
            return

        # Map AI action to a green phase (skip yellow/transition phases)
        if state.green_phases:
            desired_phase = state.green_phases[action % len(state.green_phases)]
        else:
            desired_phase = action % state.total_phases

        # First-time initialization
        if tl_id not in self.last_action:
            self.last_action[tl_id] = state.current_phase
            self.last_switch_step[tl_id] = self.current_step

        # Are we currently transitioning through yellow/all-red?
        if state.target_phase is not None:
            state.phase_timer += 1
            if state.phase_timer >= self.YELLOW_DURATION:
                # Transition complete, apply the new target green phase
                self._apply_phase(state, state.target_phase)
                state.target_phase = None
                state.phase_timer = 0
            return

        # Prevent rapid switching
        if desired_phase != self.last_action[tl_id]:
            if self.current_step - self.last_switch_step[tl_id] < self.min_green_time:
                desired_phase = self.last_action[tl_id]
            else:
                self.last_switch_step[tl_id] = self.current_step
                self.last_action[tl_id] = desired_phase

        # Trigger phase change if AI decided to switch
        if desired_phase != state.current_phase:
            # Look ahead to see if the next sequential phase is a yellow transition
            next_yellow = (state.current_phase + 1) % state.total_phases
            if next_yellow not in state.green_phases:
                # Enter transition mode
                self._apply_phase(state, next_yellow)
                state.target_phase = desired_phase
                state.phase_timer = 0
            else:
                # Fallback if no yellow phase exists
                self._apply_phase(state, desired_phase)
                state.phase_timer = 0
        else:
            state.phase_timer += 1

    # -------------------------------------------------------------
    # Phase Helpers
    # -------------------------------------------------------------

    def _next_green_phase(self, state: SignalState) -> int:
        """Find the next green phase after the current one."""
        if not state.green_phases:
            return (state.current_phase + 1) % state.total_phases

        try:
            idx = state.green_phases.index(state.current_phase)
            next_idx = (idx + 1) % len(state.green_phases)
        except ValueError:
            next_idx = 0

        return state.green_phases[next_idx]

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
                "is_green": state.current_phase in state.green_phases,
                "stagnant": state.stagnant_steps,
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

        # Skip invalid maps
        if len(env.bridge.get_traffic_light_ids()) == 0:
            env.stop()
            return

        for _ in range(steps):

            state_matrix, raw, _ = build_network_state(env.bridge, tl_order=agent.tl_ids)

            # Skip mismatched graph sizes
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
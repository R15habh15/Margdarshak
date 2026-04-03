"""
test_simulation.py
Unit tests for the simulation layer.

TraCI calls are fully mocked — no SUMO installation required.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ----------------------------------------------------------------
# SignalController
# ----------------------------------------------------------------

class TestSignalController:

    def _make_bridge(self):
        bridge = MagicMock()
        bridge.get_traffic_light_ids.return_value = ["tl_A", "tl_B", "tl_C"]
        bridge.get_tl_phase_count.return_value = 4
        bridge.get_tl_phase.return_value = 0
        return bridge

    def test_initialize_creates_signals(self):
        from src.simulation.signal_controller import SignalController, SignalMode
        bridge = self._make_bridge()
        ctrl   = SignalController(bridge, mode=SignalMode.STATIC)
        ctrl.initialize()
        assert len(ctrl.signals) == 3
        assert "tl_A" in ctrl.signals

    def test_static_step_advances_timer(self):
        from src.simulation.signal_controller import SignalController, SignalMode
        bridge = self._make_bridge()
        ctrl   = SignalController(bridge, mode=SignalMode.STATIC)
        ctrl.initialize()
        ctrl.step()
        assert ctrl.signals["tl_A"].phase_timer == 1

    def test_static_step_changes_phase_after_duration(self):
        from src.simulation.signal_controller import SignalController, SignalMode
        bridge = self._make_bridge()
        ctrl   = SignalController(bridge, mode=SignalMode.STATIC)
        ctrl.initialize()
        # Force timer to just before phase change
        for sig in ctrl.signals.values():
            sig.phase_timer = sig.phase_duration - 1
        ctrl.step()
        bridge.set_tl_phase.assert_called()

    def test_ai_step_applies_action(self):
        from src.simulation.signal_controller import SignalController, SignalMode
        bridge = self._make_bridge()
        ctrl   = SignalController(bridge, mode=SignalMode.AI)
        ctrl.initialize()
        ctrl.step(ai_actions={"tl_A": 2, "tl_B": 1, "tl_C": 3})
        bridge.set_tl_phase.assert_called()

    def test_set_mode_switches_all_signals(self):
        from src.simulation.signal_controller import SignalController, SignalMode
        bridge = self._make_bridge()
        ctrl   = SignalController(bridge, mode=SignalMode.STATIC)
        ctrl.initialize()
        ctrl.set_mode(SignalMode.AI)
        assert all(s.mode == SignalMode.AI for s in ctrl.signals.values())

    def test_force_phase_updates_signal(self):
        from src.simulation.signal_controller import SignalController, SignalMode
        bridge = self._make_bridge()
        ctrl   = SignalController(bridge, mode=SignalMode.STATIC)
        ctrl.initialize()
        ctrl.force_phase("tl_A", 2)
        bridge.set_tl_phase.assert_called_with("tl_A", 2)

    def test_force_phase_raises_for_unknown_tl(self):
        from src.simulation.signal_controller import SignalController, SignalMode
        bridge = self._make_bridge()
        ctrl   = SignalController(bridge, mode=SignalMode.STATIC)
        ctrl.initialize()
        with pytest.raises(ValueError):
            ctrl.force_phase("unknown_tl", 0)

    def test_get_all_states_returns_dict(self):
        from src.simulation.signal_controller import SignalController, SignalMode
        bridge = self._make_bridge()
        ctrl   = SignalController(bridge, mode=SignalMode.STATIC)
        ctrl.initialize()
        states = ctrl.get_all_states()
        assert isinstance(states, dict)
        assert "tl_A" in states
        assert "phase" in states["tl_A"]


# ----------------------------------------------------------------
# TraCIBridge
# ----------------------------------------------------------------

class TestTraCIBridge:

    def test_initial_state(self):
        from src.simulation.traci_bridge import TraCIBridge
        bridge = TraCIBridge()
        assert bridge.connected == False
        assert bridge.step_count == 0

    def test_step_raises_when_not_connected(self):
        from src.simulation.traci_bridge import TraCIBridge
        bridge = TraCIBridge()
        with pytest.raises(RuntimeError):
            bridge.step()

    def test_start_raises_file_not_found(self):
        from src.simulation.traci_bridge import TraCIBridge
        bridge = TraCIBridge()
        with pytest.raises(FileNotFoundError):
            bridge.start("/nonexistent/path.sumocfg")

    @patch("src.simulation.traci_bridge.traci")
    def test_stop_sets_connected_false(self, mock_traci):
        from src.simulation.traci_bridge import TraCIBridge
        bridge = TraCIBridge()
        bridge.connected = True
        bridge.stop()
        assert bridge.connected == False
        mock_traci.close.assert_called_once()

"""
conftest.py
Shared pytest fixtures for the Margadarshak test suite.
"""

import os
import sys
import pytest
import numpy as np

# Ensure backend src is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def sample_junction_features():
    """A realistic junction feature dict for testing."""
    return {
        "tl_id":              "tl_test",
        "current_phase":      1,
        "total_vehicles":     12,
        "total_queue_length": 6,
        "total_waiting_time": 45.0,
        "avg_speed":          7.5,
        "pressure":           3,
        "lanes": {
            "lane_0": {
                "vehicle_count": 6, "mean_speed": 7.5,
                "waiting_time": 22.5, "occupancy": 30.0, "queue_length": 3,
            },
            "lane_1": {
                "vehicle_count": 6, "mean_speed": 7.5,
                "waiting_time": 22.5, "occupancy": 30.0, "queue_length": 3,
            },
        },
    }


@pytest.fixture
def sample_network_features(sample_junction_features):
    """A small network of 3 junctions."""
    return {
        "tl_A": sample_junction_features,
        "tl_B": {**sample_junction_features, "tl_id": "tl_B", "total_vehicles": 5},
        "tl_C": {**sample_junction_features, "tl_id": "tl_C", "total_vehicles": 0},
    }


@pytest.fixture
def sample_state_matrix():
    """A (3, 8) float32 state matrix for 3 junctions."""
    return np.random.rand(3, 8).astype(np.float32)


@pytest.fixture
def sample_edge_index():
    """A simple graph edge index for 3 nodes."""
    return np.array([[0, 1, 2], [1, 2, 0]], dtype=np.int64)


@pytest.fixture
def drl_agent(sample_edge_index):
    """A pre-built DRL agent for testing."""
    from src.brain.drl_agent import DRLAgent
    return DRLAgent(
        tl_ids      = ["tl_A", "tl_B", "tl_C"],
        edge_index  = sample_edge_index,
        num_actions = 4,
        hidden_dim  = 32,
        gnn_out_dim = 16,
        buffer_size = 200,
        batch_size  = 8,
    )


@pytest.fixture
def mock_bridge():
    """A fully mocked TraCIBridge."""
    from unittest.mock import MagicMock
    bridge = MagicMock()
    bridge.connected                = True
    bridge.get_traffic_light_ids.return_value = ["tl_A", "tl_B", "tl_C"]
    bridge.get_tl_phase_count.return_value    = 4
    bridge.get_tl_phase.return_value          = 0
    bridge.get_lane_vehicle_count.return_value = 5
    bridge.get_lane_mean_speed.return_value    = 8.0
    bridge.get_lane_waiting_time.return_value  = 20.0
    bridge.get_lane_occupancy.return_value     = 25.0
    bridge.get_lane_queue_length.return_value  = 3
    bridge.get_simulation_time.return_value    = 100.0
    bridge.get_step.return_value               = 100
    bridge.get_active_vehicle_count.return_value = 50
    bridge.get_departed_vehicles.return_value  = 5
    bridge.get_arrived_vehicles.return_value   = 3
    bridge.is_simulation_finished.return_value = False
    return bridge

"""
test_brain.py
Unit tests for the AI brain layer — GNN, DRL agent, backpressure, replay buffer.
"""

import os
import sys
import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ----------------------------------------------------------------
# GNN Layers
# ----------------------------------------------------------------

class TestGNNLayers:

    def test_traffic_gnn_forward(self):
        import torch
        from src.brain.gnn_layers import TrafficGNN

        N, F = 5, 8
        x          = torch.randn(N, F)
        edge_index = torch.tensor([[0,1,2,3],[1,2,3,4]], dtype=torch.long)

        model = TrafficGNN(in_channels=F, hidden_dim=32, out_dim=16)
        out   = model(x, edge_index)
        assert out.shape == (N, 16)

    def test_traffic_gnn_with_head_forward(self):
        import torch
        from src.brain.gnn_layers import TrafficGNNWithHead

        N, F = 4, 8
        x          = torch.randn(N, F)
        edge_index = torch.tensor([[0,1,2],[1,2,3]], dtype=torch.long)

        model  = TrafficGNNWithHead(in_channels=F, hidden_dim=32, gnn_out_dim=16, num_actions=4)
        logits, values = model(x, edge_index)
        assert logits.shape == (N, 4)
        assert values.shape == (N, 1)

    def test_gnn_no_edges(self):
        import torch
        from src.brain.gnn_layers import TrafficGNN

        N, F = 3, 8
        x          = torch.randn(N, F)
        edge_index = torch.zeros((2, 0), dtype=torch.long)

        model = TrafficGNN(in_channels=F, hidden_dim=32, out_dim=16)
        out   = model(x, edge_index)
        assert out.shape == (N, 16)


# ----------------------------------------------------------------
# Replay Buffer
# ----------------------------------------------------------------

class TestReplayBuffer:

    def test_push_and_len(self):
        from src.brain.replay_buffer import ReplayBuffer
        buf = ReplayBuffer(capacity=100)
        assert len(buf) == 0
        buf.push(np.zeros((3,8)), [0,0,0], 1.0, np.zeros((3,8)), False)
        assert len(buf) == 1

    def test_capacity_limit(self):
        from src.brain.replay_buffer import ReplayBuffer
        buf = ReplayBuffer(capacity=5)
        for i in range(10):
            buf.push(np.zeros((2,8)), [0,0], float(i), np.zeros((2,8)), False)
        assert len(buf) == 5

    def test_sample_size(self):
        from src.brain.replay_buffer import ReplayBuffer
        buf = ReplayBuffer(capacity=100)
        for _ in range(20):
            buf.push(np.zeros((2,8)), [0,0], 1.0, np.zeros((2,8)), False)
        batch = buf.sample(10)
        assert len(batch) == 10

    def test_sample_less_than_batch(self):
        from src.brain.replay_buffer import ReplayBuffer
        buf = ReplayBuffer(capacity=100)
        for _ in range(5):
            buf.push(np.zeros((2,8)), [0,0], 1.0, np.zeros((2,8)), False)
        batch = buf.sample(20)
        assert len(batch) == 5

    def test_is_ready(self):
        from src.brain.replay_buffer import ReplayBuffer
        buf = ReplayBuffer(capacity=100)
        assert not buf.is_ready(10)
        for _ in range(10):
            buf.push(np.zeros((2,8)), [0,0], 1.0, np.zeros((2,8)), False)
        assert buf.is_ready(10)

    def test_clear(self):
        from src.brain.replay_buffer import ReplayBuffer
        buf = ReplayBuffer(capacity=100)
        for _ in range(5):
            buf.push(np.zeros((2,8)), [0,0], 1.0, np.zeros((2,8)), False)
        buf.clear()
        assert len(buf) == 0

    def test_prioritized_replay_push_sample(self):
        from src.brain.replay_buffer import PrioritizedReplayBuffer
        buf = PrioritizedReplayBuffer(capacity=100)
        for _ in range(20):
            buf.push(np.zeros((2,8)), [0,0], 1.0, np.zeros((2,8)), False)
        batch, indices, weights = buf.sample(10)
        assert len(batch)   == 10
        assert len(indices) == 10
        assert len(weights) == 10

    def test_prioritized_update_priorities(self):
        from src.brain.replay_buffer import PrioritizedReplayBuffer
        buf = PrioritizedReplayBuffer(capacity=100)
        for _ in range(20):
            buf.push(np.zeros((2,8)), [0,0], 1.0, np.zeros((2,8)), False)
        _, indices, _ = buf.sample(5)
        buf.update_priorities(indices, np.ones(5) * 0.5)


# ----------------------------------------------------------------
# DRL Agent
# ----------------------------------------------------------------

class TestDRLAgent:

    def _make_agent(self):
        from src.brain.drl_agent import DRLAgent
        tl_ids     = ["tl_A", "tl_B", "tl_C"]
        edge_index = np.array([[0,1,2],[1,2,0]], dtype=np.int64)
        return DRLAgent(
            tl_ids      = tl_ids,
            edge_index  = edge_index,
            num_actions = 4,
            hidden_dim  = 32,
            gnn_out_dim = 16,
            buffer_size = 500,
            batch_size  = 8,
        )

    def test_select_actions_returns_dict(self):
        agent        = self._make_agent()
        state_matrix = np.random.rand(3, 8).astype(np.float32)
        actions      = agent.select_actions(state_matrix)
        assert isinstance(actions, dict)
        assert set(actions.keys()) == {"tl_A", "tl_B", "tl_C"}

    def test_select_actions_valid_phases(self):
        agent        = self._make_agent()
        state_matrix = np.random.rand(3, 8).astype(np.float32)
        actions      = agent.select_actions(state_matrix)
        for phase in actions.values():
            assert 0 <= phase < 4

    def test_select_actions_greedy(self):
        agent        = self._make_agent()
        state_matrix = np.random.rand(3, 8).astype(np.float32)
        actions      = agent.select_actions(state_matrix, greedy=True)
        assert len(actions) == 3

    def test_store_transition(self):
        agent        = self._make_agent()
        state        = np.random.rand(3, 8).astype(np.float32)
        actions      = {"tl_A": 0, "tl_B": 1, "tl_C": 2}
        agent.store_transition(state, actions, 1.0, state, False)
        assert len(agent.replay) == 1

    def test_train_step_returns_none_if_buffer_small(self):
        agent  = self._make_agent()
        result = agent.train_step()
        assert result is None

    def test_train_step_returns_loss_when_ready(self):
        agent = self._make_agent()
        state = np.random.rand(3, 8).astype(np.float32)
        for _ in range(20):
            agent.store_transition(state, {"tl_A":0,"tl_B":1,"tl_C":2}, 1.0, state, False)
        loss = agent.train_step()
        assert loss is not None
        assert isinstance(loss, float)

    def test_compute_reward(self):
        agent = self._make_agent()
        raw_features = {
            "tl_A": {"total_waiting_time": 30.0, "total_queue_length": 5, "avg_speed": 8.0, "pressure": 2},
            "tl_B": {"total_waiting_time": 20.0, "total_queue_length": 3, "avg_speed": 9.0, "pressure": 1},
        }
        reward = agent.compute_reward(raw_features)
        assert isinstance(reward, float)

    def test_save_and_load(self, tmp_path):
        import torch
        agent    = self._make_agent()
        filename = "test_model.pt"

        # Patch models dir to tmp_path
        import src.brain.drl_agent as da
        original = da.MODELS_DIR
        da.MODELS_DIR = str(tmp_path)

        agent.save(filename)
        assert (tmp_path / filename).exists()
        agent.load(filename)

        da.MODELS_DIR = original


# ----------------------------------------------------------------
# Backpressure
# ----------------------------------------------------------------

class TestBackpressure:

    def test_compute_network_pressure_returns_dict(self):
        from src.brain.backpressure import compute_network_pressure
        from unittest.mock import MagicMock

        bridge = MagicMock()
        bridge.get_traffic_light_ids.return_value = ["tl_A", "tl_B"]
        bridge.get_tl_phase_count.return_value = 4
        bridge.get_tl_phase.return_value = 0

        with __import__("unittest.mock", fromlist=["patch"]).patch("src.brain.backpressure.traci") as mock_traci:
            mock_traci.trafficlight.getAllProgramLogics.return_value = []
            result = compute_network_pressure(bridge)

        assert isinstance(result, dict)

    def test_select_best_phase_returns_int(self):
        from src.brain.backpressure import select_best_phase
        from unittest.mock import patch, MagicMock

        with patch("src.brain.backpressure.traci") as mock_traci:
            mock_traci.trafficlight.getAllProgramLogics.return_value = []
            result = select_best_phase("tl_A", 4)

        assert isinstance(result, int)
        assert 0 <= result < 4

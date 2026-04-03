"""
drl_agent.py
Deep Reinforcement Learning agent for multi-city traffic control.

Architecture
------------
- Single GNN trained on the unified node set (all cities merged).
- Each transition carries a node_mask that marks which nodes were
  active in the city that generated it.
- Loss is computed only over active nodes (mask-weighted SmoothL1).
- Action selection returns actions only for active TL IDs; absent
  nodes receive a no-op action of 0 (ignored by SignalController).
- Reward computation lives in RewardCalculator (rewards/reward_calculator.py),
  not here. The agent only stores and learns from whatever scalar it receives.
"""

import os
import logging
import random
import numpy as np
from collections import deque
from typing import List, Dict, Optional

import torch
import torch.nn as nn
import torch.optim as optim

from .gnn_layers import TrafficGNNWithHead
from ..sensing.state_vector import STATE_DIM

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(__file__), "../../models")
os.makedirs(MODELS_DIR, exist_ok=True)

MODEL_FILE = "rl_policy.pt"


# ===============================================================
# Replay Buffer  (stores node_mask alongside each transition)
# ===============================================================

class ReplayBuffer:

    def __init__(self, capacity: int = 20000):
        self.buffer = deque(maxlen=capacity)

    def push(
        self,
        state      : np.ndarray,   # (N, STATE_DIM)
        action     : list,          # length N, int per node
        reward     : float,
        next_state : np.ndarray,   # (N, STATE_DIM)
        done       : bool,
        node_mask  : np.ndarray,   # (N,) bool
    ):
        self.buffer.append((state, action, reward, next_state, done, node_mask))

    def sample(self, batch_size: int):
        batch = random.sample(self.buffer, min(batch_size, len(self.buffer)))
        states, actions, rewards, next_states, dones, masks = zip(*batch)
        return states, actions, rewards, next_states, dones, masks

    def __len__(self):
        return len(self.buffer)


# ===============================================================
# DRL Agent
# ===============================================================

class DRLAgent:

    def __init__(
        self,
        tl_ids          : List[str],
        edge_index,                       # (2, E) np.ndarray or list
        num_actions     : int   = 4,
        hidden_dim      : int   = 128,
        gnn_out_dim     : int   = 64,
        lr              : float = 1e-3,
        gamma           : float = 0.95,
        epsilon         : float = 1.0,
        epsilon_min     : float = 0.02,
        epsilon_decay   : float = 0.995,  # slower decay — more exploration
        buffer_size     : int   = 20000,
        batch_size      : int   = 64,
        target_update_freq : int = 500,
    ):
        self.tl_ids    = tl_ids
        self.num_nodes = len(tl_ids)
        self.tl_index  = {tid: i for i, tid in enumerate(tl_ids)}
        self.num_actions = num_actions

        self.gamma         = gamma
        self.epsilon       = epsilon
        self.epsilon_min   = epsilon_min
        self.epsilon_decay = epsilon_decay

        self.batch_size          = batch_size
        self.target_update_freq  = target_update_freq
        self.step_count          = 0

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"DRLAgent using device: {self.device}")

        self.edge_index = torch.tensor(
            edge_index, dtype=torch.long
        ).to(self.device)

        self.online_net = TrafficGNNWithHead(
            in_channels = STATE_DIM,
            hidden_dim  = hidden_dim,
            gnn_out_dim = gnn_out_dim,
            num_actions = num_actions,
        ).to(self.device)

        self.target_net = TrafficGNNWithHead(
            in_channels = STATE_DIM,
            hidden_dim  = hidden_dim,
            gnn_out_dim = gnn_out_dim,
            num_actions = num_actions,
        ).to(self.device)

        self.target_net.load_state_dict(self.online_net.state_dict())
        self.target_net.eval()

        self.optimizer = optim.Adam(self.online_net.parameters(), lr=lr)
        self.loss_fn   = nn.SmoothL1Loss(reduction="none")   # per-element — masked below

        self.replay = ReplayBuffer(buffer_size)

        self._auto_load_model()

    # -----------------------------------------------------------
    # Model persistence
    # -----------------------------------------------------------

    def _auto_load_model(self):

        path = os.path.join(MODELS_DIR, MODEL_FILE)

        if not os.path.exists(path):
            logger.warning("No trained DRL model found. Starting fresh.")
            return

        try:
            ckpt = torch.load(path, map_location=self.device)
            self.online_net.load_state_dict(ckpt["online_net"])
            self.target_net.load_state_dict(ckpt["target_net"])
            self.epsilon    = ckpt.get("epsilon",    self.epsilon_min)
            self.step_count = ckpt.get("step_count", 0)
            logger.info(f"Loaded DRL model from {path}")
        except Exception as e:
            logger.warning(f"Model load failed ({e}). Starting fresh.")

    def save(self):

        path = os.path.join(MODELS_DIR, MODEL_FILE)

        torch.save({
            "online_net" : self.online_net.state_dict(),
            "target_net" : self.target_net.state_dict(),
            "epsilon"    : self.epsilon,
            "step_count" : self.step_count,
        }, path)

        logger.info(f"DRL model saved: {path}")

    # -----------------------------------------------------------
    # Action selection
    # -----------------------------------------------------------

    def select_actions(
        self,
        state_matrix : np.ndarray,           # (N, STATE_DIM)
        node_mask    : Optional[np.ndarray] = None,  # (N,) bool
        greedy       : bool = False,
    ) -> Dict[str, int]:
        """
        Returns a dict {tl_id -> phase_action} for ACTIVE nodes only.
        Absent nodes (mask=False) are omitted — SignalController ignores them.
        """

        active_ids = (
            [tid for tid in self.tl_ids if node_mask[self.tl_index[tid]]]
            if node_mask is not None
            else self.tl_ids
        )

        # Epsilon-greedy exploration over active nodes only
        if not greedy and random.random() < self.epsilon:
            return {
                tid: random.randint(0, self.num_actions - 1)
                for tid in active_ids
            }

        self.online_net.eval()

        with torch.no_grad():
            x = torch.tensor(
                state_matrix, dtype=torch.float32
            ).to(self.device)                           # (N, STATE_DIM)

            q_values, _ = self.online_net(x, self.edge_index)  # (N, num_actions)

            actions = {}
            for tid in active_ids:
                idx           = self.tl_index[tid]
                actions[tid]  = int(torch.argmax(q_values[idx]).item())

        return actions

    # -----------------------------------------------------------
    # Transition storage
    # (Reward is computed externally by RewardCalculator in the worker)
    # -----------------------------------------------------------

    def store_transition(
        self,
        state      : np.ndarray,
        actions    : Dict[str, int],
        reward     : float,
        next_state : np.ndarray,
        done       : bool,
        node_mask  : np.ndarray,
    ):
        action_vec = [actions.get(tid, 0) for tid in self.tl_ids]
        self.replay.push(state, action_vec, reward, next_state, done, node_mask)

    # -----------------------------------------------------------
    # Training
    # -----------------------------------------------------------

    def train_step(self) -> Optional[float]:

        if len(self.replay) < self.batch_size:
            return None

        states, actions, rewards, next_states, dones, masks = \
            self.replay.sample(self.batch_size)

        rewards = torch.tensor(rewards, dtype=torch.float32).to(self.device)  # (B,)
        dones   = torch.tensor(dones,   dtype=torch.float32).to(self.device)  # (B,)
        actions = torch.tensor(actions, dtype=torch.long).to(self.device)     # (B, N)

        self.online_net.train()

        q_values_list = []
        q_next_list   = []
        mask_list     = []
        valid_idx     = []

        for i in range(len(states)):

            state      = torch.tensor(states[i],      dtype=torch.float32).to(self.device)
            next_state = torch.tensor(next_states[i], dtype=torch.float32).to(self.device)

            # Guard: must be exactly (N, STATE_DIM)
            if state.dim() != 2 or state.shape[0] != self.num_nodes:
                continue
            if next_state.dim() != 2 or next_state.shape[0] != self.num_nodes:
                continue

            q_vals, _ = self.online_net(state, self.edge_index)
            q_values_list.append(q_vals)

            with torch.no_grad():
                q_next, _ = self.target_net(next_state, self.edge_index)
                q_next_list.append(q_next)

            # Convert node_mask to float tensor for loss weighting
            mask_tensor = torch.tensor(
                masks[i], dtype=torch.float32
            ).to(self.device)                   # (N,)
            mask_list.append(mask_tensor)

            valid_idx.append(i)

        if not q_values_list:
            return None

        q_values = torch.stack(q_values_list)   # (B, N, A)
        q_next   = torch.stack(q_next_list)     # (B, N, A)
        masks_t  = torch.stack(mask_list)       # (B, N)

        vidx      = torch.tensor(valid_idx, dtype=torch.long)
        rewards_v = rewards[vidx]               # (B,)
        dones_v   = dones[vidx]                 # (B,)
        actions_v = actions[vidx]               # (B, N)

        # Q-values for chosen actions
        q_taken = q_values.gather(
            2, actions_v.unsqueeze(2)
        ).squeeze(2)                            # (B, N)

        # Double-DQN target
        with torch.no_grad():
            best_actions = q_values.argmax(dim=2, keepdim=True)   # (B, N, 1)
            q_next_best  = q_next.gather(2, best_actions).squeeze(2)  # (B, N)

        q_target = (
            rewards_v.unsqueeze(1)
            + self.gamma * q_next_best * (1.0 - dones_v.unsqueeze(1))
        )                                       # (B, N)

        # Element-wise SmoothL1, then zero-out absent nodes
        element_loss  = self.loss_fn(q_taken, q_target)   # (B, N)
        masked_loss   = element_loss * masks_t             # zero where node absent
        active_count  = masks_t.sum().clamp(min=1.0)
        loss          = masked_loss.sum() / active_count   # mean over active nodes

        if torch.isnan(loss):
            return None

        self.optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.online_net.parameters(), 1.0)
        self.optimizer.step()

        self.epsilon    = max(self.epsilon_min, self.epsilon * self.epsilon_decay)
        self.step_count += 1

        if self.step_count % self.target_update_freq == 0:
            self.target_net.load_state_dict(self.online_net.state_dict())
            logger.debug(f"Target network updated at step {self.step_count}")

        return float(loss.item())
"""
replay_buffer.py
Experience replay buffer for the DQN training pipeline.

Provides:
  - Standard uniform random replay buffer
  - Prioritized Experience Replay (PER) buffer
    Samples transitions with higher TD-error more frequently,
    accelerating learning on rare but important experiences.

Both share the same push/sample interface so they can be swapped
in DRLAgent without code changes.
"""

import random
import logging
import numpy as np
from collections import deque
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


# ================================================================
# Uniform Replay Buffer
# ================================================================

class ReplayBuffer:
    """
    Standard fixed-size uniform experience replay buffer.

    Stores (state, action, reward, next_state, done) transitions
    and samples random mini-batches for DQN training.

    Args:
        capacity: Maximum number of transitions to store
    """

    def __init__(self, capacity: int = 20_000):
        self.buffer   = deque(maxlen=capacity)
        self.capacity = capacity

    def push(
        self,
        state:      np.ndarray,
        action:     List[int],
        reward:     float,
        next_state: np.ndarray,
        done:       bool,
    ):
        """Store a single transition."""
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size: int) -> List[Tuple]:
        """Sample a random mini-batch of transitions."""
        size = min(batch_size, len(self.buffer))
        return random.sample(self.buffer, size)

    def sample_arrays(self, batch_size: int):
        """
        Sample a mini-batch and return as stacked numpy arrays.

        Returns:
            states, actions, rewards, next_states, dones
            all as numpy arrays
        """
        batch = self.sample(batch_size)
        states, actions, rewards, next_states, dones = zip(*batch)
        return (
            np.array(states,      dtype=np.float32),
            np.array(actions,     dtype=np.int64),
            np.array(rewards,     dtype=np.float32),
            np.array(next_states, dtype=np.float32),
            np.array(dones,       dtype=np.float32),
        )

    def __len__(self) -> int:
        return len(self.buffer)

    def is_ready(self, batch_size: int) -> bool:
        """Return True if buffer has enough samples to train."""
        return len(self.buffer) >= batch_size

    def clear(self):
        self.buffer.clear()


# ================================================================
# Prioritized Experience Replay (PER)
# ================================================================

class PrioritizedReplayBuffer:
    """
    Prioritized Experience Replay buffer.

    Transitions with higher TD-error are sampled more frequently.
    Importance sampling weights correct for the introduced bias.

    Args:
        capacity:  Maximum buffer size
        alpha:     Priority exponent (0 = uniform, 1 = full priority)
        beta_start: Initial importance sampling weight
        beta_end:   Final importance sampling weight (annealed to 1.0)
        beta_steps: Steps over which beta is annealed
        epsilon:   Small constant to ensure non-zero priorities
    """

    def __init__(
        self,
        capacity:    int   = 20_000,
        alpha:       float = 0.6,
        beta_start:  float = 0.4,
        beta_end:    float = 1.0,
        beta_steps:  int   = 100_000,
        epsilon:     float = 1e-5,
    ):
        self.capacity   = capacity
        self.alpha      = alpha
        self.beta       = beta_start
        self.beta_end   = beta_end
        self.beta_inc   = (beta_end - beta_start) / beta_steps
        self.epsilon    = epsilon

        self.buffer     = []
        self.priorities = np.zeros(capacity, dtype=np.float32)
        self.pos        = 0
        self._size      = 0

    def push(
        self,
        state:      np.ndarray,
        action:     List[int],
        reward:     float,
        next_state: np.ndarray,
        done:       bool,
    ):
        """Store transition with max priority."""
        max_priority = self.priorities[:self._size].max() if self._size > 0 else 1.0

        if self._size < self.capacity:
            self.buffer.append((state, action, reward, next_state, done))
            self._size += 1
        else:
            self.buffer[self.pos] = (state, action, reward, next_state, done)

        self.priorities[self.pos] = max_priority
        self.pos = (self.pos + 1) % self.capacity

    def sample(self, batch_size: int):
        """
        Sample a prioritized mini-batch.

        Returns:
            batch:    List of transition tuples
            indices:  Indices for priority update
            weights:  Importance sampling weights
        """
        if self._size == 0:
            return [], [], np.array([])

        probs = self.priorities[:self._size] ** self.alpha
        probs /= probs.sum()

        size    = min(batch_size, self._size)
        indices = np.random.choice(self._size, size, p=probs, replace=False)
        batch   = [self.buffer[i] for i in indices]

        # Importance sampling weights
        weights = (self._size * probs[indices]) ** (-self.beta)
        weights /= weights.max()

        # Anneal beta toward 1.0
        self.beta = min(self.beta_end, self.beta + self.beta_inc)

        return batch, indices, weights.astype(np.float32)

    def update_priorities(self, indices: np.ndarray, td_errors: np.ndarray):
        """Update priorities based on new TD-errors."""
        for idx, err in zip(indices, td_errors):
            self.priorities[idx] = abs(err) + self.epsilon

    def __len__(self) -> int:
        return self._size

    def is_ready(self, batch_size: int) -> bool:
        return self._size >= batch_size

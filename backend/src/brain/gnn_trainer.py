"""
gnn_trainer.py
Training loop for the GNN-based DQN agent.

Manages the full training pipeline:
  - Episode loop over simulation runs
  - State extraction + action selection + environment stepping
  - Reward computation
  - Experience storage + mini-batch training
  - Periodic model checkpointing
  - Training metrics logging

Can be run as a standalone training script or called from the API.
"""

import logging
import time
from typing import Optional, Dict, List
from dataclasses import dataclass, field

from ..simulation.traffic_env import TrafficEnv
from ..simulation.signal_controller import SignalMode
from ..sensing.state_vector import build_network_state
from .reward_calculator import RewardCalculator
from ..sensing.congestion_detector import detect_network_congestion
from ..utils.graph_builder import load_sumo_network, build_tl_graph, build_pyg_data
from .drl_agent import DRLAgent
from .model_manager import ModelManager

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Hyperparameters and settings for a training run."""
    config_path:        str             # Path to .sumocfg file
    net_path:           str             # Path to .net.xml file
    num_episodes:       int   = 50
    max_steps_per_ep:   int   = 3600    # Max simulation steps per episode
    num_actions:        int   = 4       # Max signal phases
    hidden_dim:         int   = 64
    gnn_out_dim:        int   = 32
    lr:                 float = 1e-3
    gamma:              float = 0.95
    epsilon_start:      float = 1.0
    epsilon_min:        float = 0.05
    epsilon_decay:      float = 0.995
    buffer_size:        int   = 20_000
    batch_size:         int   = 64
    target_update_freq: int   = 100
    checkpoint_freq:    int   = 10      # Save checkpoint every N episodes
    train_every:        int   = 4       # Train every N simulation steps
    traci_port:         int   = 8813


@dataclass
class TrainingMetrics:
    """Aggregated metrics collected across training."""
    episode_rewards:     List[float] = field(default_factory=list)
    episode_wait_times:  List[float] = field(default_factory=list)
    episode_arrived:     List[int]   = field(default_factory=list)
    losses:              List[float] = field(default_factory=list)
    best_reward:         float       = float("-inf")
    best_episode:        int         = 0


class GNNTrainer:
    """
    Orchestrates the full training loop for the DQN traffic control agent.

    Usage:
        config  = TrainingConfig(config_path="...", net_path="...")
        trainer = GNNTrainer(config)
        trainer.train()
    """

    def __init__(self, config: TrainingConfig):
        self.config       = config
        self.metrics      = TrainingMetrics()
        self.model_manager = ModelManager()
        self.reward_calc  = RewardCalculator()
        self._stop_flag   = False

        # Build graph structure from the road network
        logger.info("Loading road network for graph construction...")
        net = load_sumo_network(config.net_path)

        # We need TL IDs — start a temporary env to get them
        self._tl_ids, self._edge_index, self._positions =             self._init_graph(net, config)

        # Instantiate the DRL agent
        self.agent = DRLAgent(
            tl_ids           = self._tl_ids,
            edge_index       = self._edge_index,
            num_actions      = config.num_actions,
            hidden_dim       = config.hidden_dim,
            gnn_out_dim      = config.gnn_out_dim,
            lr               = config.lr,
            gamma            = config.gamma,
            epsilon          = config.epsilon_start,
            epsilon_min      = config.epsilon_min,
            epsilon_decay    = config.epsilon_decay,
            buffer_size      = config.buffer_size,
            batch_size       = config.batch_size,
            target_update_freq = config.target_update_freq,
        )

        logger.info(
            f"GNNTrainer initialized | "
            f"junctions={len(self._tl_ids)} | "
            f"graph_edges={self._edge_index.shape[1]}"
        )

    # ------------------------------------------------------------------
    # Training Loop
    # ------------------------------------------------------------------

    def train(self) -> TrainingMetrics:
        """
        Run the full training loop across all episodes.

        Returns:
            TrainingMetrics collected across all episodes
        """
        logger.info(f"Starting training: {self.config.num_episodes} episodes")
        self._stop_flag = False

        for episode in range(1, self.config.num_episodes + 1):
            if self._stop_flag:
                logger.info("Training stopped by external signal.")
                break

            ep_metrics = self._run_episode(episode)
            self._update_metrics(episode, ep_metrics)

            # Periodic checkpoint
            if episode % self.config.checkpoint_freq == 0:
                self.model_manager.save_checkpoint(
                    self.agent, episode, ep_metrics
                )

            self._log_episode(episode, ep_metrics)

        # Save final inference model
        self.model_manager.save_inference_model(self.agent)
        logger.info("Training complete. Final model saved.")
        return self.metrics

    def stop(self):
        """Signal the training loop to stop after the current episode."""
        self._stop_flag = True

    # ------------------------------------------------------------------
    # Episode
    # ------------------------------------------------------------------

    def _run_episode(self, episode: int) -> dict:
        """Run a single training episode."""
        env = TrafficEnv(
            config_path = self.config.config_path,
            mode        = SignalMode.AI,
        )
        env.start(port=self.config.traci_port)
        self.reward_calc.reset()

        total_reward = 0.0
        total_loss   = 0.0
        loss_count   = 0
        step         = 0

        # Initial state
        state_matrix, raw_features, _ = build_network_state(
            env.bridge, tl_order=self._tl_ids
        )

        while not env.is_done() and step < self.config.max_steps_per_ep:
            # Select actions
            actions = self.agent.select_actions(state_matrix)

            # Step simulation
            sim_state = env.step(ai_actions=actions)

            # Next state
            next_matrix, next_features, _ = build_network_state(
                env.bridge, tl_order=self._tl_ids
            )

            # Compute reward
            current_phases = {tid: actions[tid] for tid in self._tl_ids}
            reward = self.reward_calc.scalar(next_features, sim_state, current_phases)
            done   = env.is_done()

            # Store transition
            self.agent.store_transition(state_matrix, actions, reward, next_matrix, done)

            # Train every N steps
            if step % self.config.train_every == 0:
                loss = self.agent.train_step()
                if loss is not None:
                    total_loss  += loss
                    loss_count  += 1

            total_reward  += reward
            state_matrix   = next_matrix
            raw_features   = next_features
            step          += 1

        summary = env.get_metrics_summary()
        env.stop()

        return {
            "total_reward":    round(total_reward, 4),
            "avg_loss":        round(total_loss / max(loss_count, 1), 6),
            "total_wait":      summary["total_waiting_time"],
            "total_arrived":   summary["total_arrived"],
            "steps":           step,
            "epsilon":         self.agent.epsilon,
        }

    # ------------------------------------------------------------------
    # Graph Init
    # ------------------------------------------------------------------

    def _init_graph(self, net, config: TrainingConfig):
        """
        Start a brief simulation to get TL IDs then build the graph.
        """
        import traci
        env = TrafficEnv(config_path=config.config_path, mode=SignalMode.STATIC)
        env.start(port=config.traci_port)
        tl_ids = env.bridge.get_traffic_light_ids()
        env.stop()

        import time; time.sleep(0.5)

        positions, edge_index, tl_index_map = build_tl_graph(net, tl_ids)
        ordered_ids = sorted(tl_ids)
        return ordered_ids, edge_index, positions

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def _update_metrics(self, episode: int, ep_metrics: dict):
        self.metrics.episode_rewards.append(ep_metrics["total_reward"])
        self.metrics.episode_wait_times.append(ep_metrics["total_wait"])
        self.metrics.episode_arrived.append(ep_metrics["total_arrived"])

        if ep_metrics["avg_loss"] > 0:
            self.metrics.losses.append(ep_metrics["avg_loss"])

        if ep_metrics["total_reward"] > self.metrics.best_reward:
            self.metrics.best_reward  = ep_metrics["total_reward"]
            self.metrics.best_episode = episode

    def _log_episode(self, episode: int, ep_metrics: dict):
        logger.info(
            f"Episode {episode:3d}/{self.config.num_episodes} | "
            f"Reward: {ep_metrics['total_reward']:+.2f} | "
            f"Wait: {ep_metrics['total_wait']:.0f}s | "
            f"Arrived: {ep_metrics['total_arrived']} | "
            f"Loss: {ep_metrics['avg_loss']:.5f} | "
            f"Epsilon: {ep_metrics['epsilon']:.3f}"
        )

    def get_training_summary(self) -> dict:
        """Return a JSON-serializable training summary."""
        return {
            "total_episodes":    len(self.metrics.episode_rewards),
            "best_reward":       self.metrics.best_reward,
            "best_episode":      self.metrics.best_episode,
            "avg_reward_last10": (
                sum(self.metrics.episode_rewards[-10:]) /
                min(len(self.metrics.episode_rewards), 10)
            ) if self.metrics.episode_rewards else 0.0,
            "episode_rewards":   self.metrics.episode_rewards,
            "episode_waits":     self.metrics.episode_wait_times,
            "losses":            self.metrics.losses,
        }

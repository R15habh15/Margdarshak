"""
model_manager.py
Manages saving, loading, and versioning of trained AI models.

Responsibilities:
  - Save full training checkpoints (weights + optimizer + metadata)
  - Load models for inference
  - List available saved models
  - Track training progress across sessions
  - Export lightweight inference-only models
"""

import os
import json
import logging
import datetime
import torch
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

MODELS_DIR = os.path.join(os.path.dirname(__file__), "../../models")
os.makedirs(MODELS_DIR, exist_ok=True)

CHECKPOINT_DIR = os.path.join(MODELS_DIR, "checkpoints")
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

METADATA_FILE = os.path.join(MODELS_DIR, "training_log.json")


class ModelManager:
    """
    Handles all model persistence operations for Margadarshak.

    Supports:
      - Full checkpoints (for resuming training)
      - Inference snapshots (lightweight, weights only)
      - Training history logging
    """

    def __init__(self, models_dir: str = MODELS_DIR):
        self.models_dir     = models_dir
        self.checkpoint_dir = os.path.join(models_dir, "checkpoints")
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        self._training_log  = self._load_training_log()

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------

    def save_checkpoint(
        self,
        agent,
        episode:      int,
        metrics:      Dict[str, Any],
        tag:          str = "latest",
    ) -> str:
        """
        Save a full training checkpoint.
        """
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename  = f"checkpoint_{tag}_ep{episode}_{timestamp}.pt"
        path      = os.path.join(self.checkpoint_dir, filename)

        checkpoint = {
            "episode":      episode,
            "step_count":   agent.step_count,
            "epsilon":      agent.epsilon,
            "online_net":   agent.online_net.state_dict(),
            "target_net":   agent.target_net.state_dict(),
            "optimizer":    agent.optimizer.state_dict(),
            "metrics":      metrics,
            "tl_ids":       agent.tl_ids,
            "num_actions":  agent.num_actions,
            "timestamp":    timestamp,
        }

        torch.save(checkpoint, path)
        logger.info(f"Checkpoint saved: {path}")

        self._cleanup_old_checkpoints(tag, keep=3)
        self._log_training_entry(episode, metrics, path)

        return path

    def save_inference_model(self, agent, filename: str = "rl_policy.pt"):
        """
        Save lightweight inference model.
        """

        path = os.path.join(self.models_dir, filename)

        torch.save(
            {
                "encoder": agent.encoder.state_dict(),
                "heads": agent.heads.state_dict(),
                "epsilon": agent.epsilon,
            },
            path,
        )

        logger.info(f"Inference model saved: {path}")

        return path
    def save_gnn_model(self, gnn_model, filename: str = "gnn_model.pt") -> str:
        """Save GNN model weights independently."""
        path = os.path.join(self.models_dir, filename)
        torch.save(gnn_model.state_dict(), path)
        logger.info(f"GNN model saved: {path}")
        return path

    # ------------------------------------------------------------------
    # Load
    # ------------------------------------------------------------------

    def load_checkpoint(self, agent, path: str) -> Dict[str, Any]:
        """
        Load a full checkpoint into an agent.
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Checkpoint not found: {path}")

        ckpt = torch.load(path, map_location=agent.device)
        agent.online_net.load_state_dict(ckpt["online_net"])
        agent.target_net.load_state_dict(ckpt["target_net"])
        agent.optimizer.load_state_dict(ckpt["optimizer"])
        agent.epsilon    = ckpt.get("epsilon", agent.epsilon_min)
        agent.step_count = ckpt.get("step_count", 0)

        logger.info(f"Checkpoint loaded: {path} (episode {ckpt.get('episode', '?')})")
        return ckpt

    def load_latest_checkpoint(self, agent, tag: str = "latest") -> Optional[Dict]:
        """Load the most recent checkpoint matching a tag."""
        checkpoints = self.list_checkpoints(tag=tag)
        if not checkpoints:
            logger.warning(f"No checkpoints found for tag '{tag}'")
            return None
        latest = checkpoints[-1]
        return self.load_checkpoint(agent, os.path.join(self.checkpoint_dir, latest))
    def load_inference_model(self, agent, filename: str = "rl_policy.pt"):

        path = os.path.join(self.models_dir, filename)

        if not os.path.exists(path):
            logger.warning(
                f"No trained model found at {path}. "
                "Continuing with randomly initialized DRL agent."
            )
            return False

        try:

            ckpt = torch.load(path, map_location=agent.device)

            agent.encoder.load_state_dict(ckpt["encoder"])
            agent.heads.load_state_dict(ckpt["heads"])

            agent.epsilon = ckpt.get("epsilon", agent.epsilon_min)

            logger.info(f"Inference model loaded: {path}")

            return True

        except Exception as e:

            logger.warning(
                f"Failed to load inference model ({e}). "
                "Using randomly initialized DRL agent."
            )

            return False
    # ------------------------------------------------------------------
    # Listing & Cleanup
    # ------------------------------------------------------------------

    def list_checkpoints(self, tag: Optional[str] = None) -> List[str]:
        """Return sorted list of checkpoint filenames, optionally filtered by tag."""
        files = sorted([
            f for f in os.listdir(self.checkpoint_dir)
            if f.endswith(".pt") and (tag is None or tag in f)
        ])
        return files

    def list_models(self) -> Dict[str, list]:
        """Return all available models and checkpoints."""
        inference = [f for f in os.listdir(self.models_dir) if f.endswith(".pt")]
        checkpoints = self.list_checkpoints()
        return {
            "inference_models": inference,
            "checkpoints":      checkpoints,
        }

    def _cleanup_old_checkpoints(self, tag: str, keep: int = 3):
        """Remove old checkpoints for a tag, keeping only the N most recent."""
        tagged = self.list_checkpoints(tag=tag)
        to_delete = tagged[:-keep] if len(tagged) > keep else []
        for f in to_delete:
            path = os.path.join(self.checkpoint_dir, f)
            os.remove(path)
            logger.debug(f"Deleted old checkpoint: {path}")

    # ------------------------------------------------------------------
    # Training Log
    # ------------------------------------------------------------------

    def _load_training_log(self) -> list:
        if os.path.exists(METADATA_FILE):
            try:
                with open(METADATA_FILE) as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _log_training_entry(self, episode: int, metrics: dict, checkpoint_path: str):
        entry = {
            "episode":    episode,
            "metrics":    metrics,
            "checkpoint": checkpoint_path,
            "timestamp":  datetime.datetime.utcnow().isoformat(),
        }
        self._training_log.append(entry)
        try:
            with open(METADATA_FILE, "w") as f:
                json.dump(self._training_log, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not write training log: {e}")

    def get_training_history(self) -> list:
        """Return the full training history log."""
        return self._training_log
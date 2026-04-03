"""
training_api.py
REST API endpoints for triggering and monitoring AI model training.

Endpoints:
  POST /api/training/start      — start a training run (background task)
  POST /api/training/stop       — stop the current training run
  GET  /api/training/status     — training progress and current metrics
  GET  /api/training/history    — full training episode history
  GET  /api/training/models     — list all saved models and checkpoints
  POST /api/training/load       — load a saved model into the active agent
"""

import logging
import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from ..brain.gnn_trainer import GNNTrainer, TrainingConfig
from ..brain.model_manager import ModelManager

logger = logging.getLogger(__name__)
router = APIRouter()

# Shared training state
_trainer: Optional[GNNTrainer] = None
_training_active: bool          = False
_training_summary: dict         = {}
_model_manager = ModelManager()


# ----------------------------------------------------------------
# Request Models
# ----------------------------------------------------------------

class StartTrainingRequest(BaseModel):
    config_path:        str
    net_path:           str
    num_episodes:       int   = 50
    max_steps_per_ep:   int   = 3600
    num_actions:        int   = 4
    hidden_dim:         int   = 64
    lr:                 float = 1e-3
    gamma:              float = 0.95
    epsilon_start:      float = 1.0
    epsilon_min:        float = 0.05
    batch_size:         int   = 64
    checkpoint_freq:    int   = 10
    traci_port:         int   = 8813

class LoadModelRequest(BaseModel):
    filename: str   # e.g. "rl_policy.pt"


# ----------------------------------------------------------------
# Background Training Task
# ----------------------------------------------------------------

async def _run_training(config: TrainingConfig):
    """Background coroutine that runs the training loop."""
    global _trainer, _training_active, _training_summary

    _training_active = True
    try:
        loop = asyncio.get_event_loop()
        # Run blocking training in thread pool so API stays responsive
        metrics = await loop.run_in_executor(None, _trainer.train)
        _training_summary = _trainer.get_training_summary()
        logger.info("Background training completed.")
    except Exception as e:
        logger.error(f"Training error: {e}")
        _training_summary = {"error": str(e)}
    finally:
        _training_active = False


# ----------------------------------------------------------------
# Endpoints
# ----------------------------------------------------------------

@router.post("/start")
async def start_training(
    req: StartTrainingRequest,
    background_tasks: BackgroundTasks,
):
    """Start AI training in the background."""
    global _trainer, _training_active

    if _training_active:
        raise HTTPException(status_code=409, detail="Training is already running.")

    config = TrainingConfig(
        config_path      = req.config_path,
        net_path         = req.net_path,
        num_episodes     = req.num_episodes,
        max_steps_per_ep = req.max_steps_per_ep,
        num_actions      = req.num_actions,
        hidden_dim       = req.hidden_dim,
        lr               = req.lr,
        gamma            = req.gamma,
        epsilon_start    = req.epsilon_start,
        epsilon_min      = req.epsilon_min,
        batch_size       = req.batch_size,
        checkpoint_freq  = req.checkpoint_freq,
        traci_port       = req.traci_port,
    )

    try:
        _trainer = GNNTrainer(config)
        background_tasks.add_task(_run_training, config)
        return {
            "status":   "training_started",
            "episodes": req.num_episodes,
            "message":  "Training running in background. Poll /status for progress.",
        }
    except Exception as e:
        logger.error(f"Failed to initialize trainer: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_training():
    """Signal the training loop to stop after the current episode."""
    global _trainer, _training_active
    if not _training_active or not _trainer:
        raise HTTPException(status_code=400, detail="No training is currently running.")
    _trainer.stop()
    return {"status": "stop_requested", "message": "Training will stop after current episode."}


@router.get("/status")
async def get_training_status():
    """Return current training status and latest metrics."""
    global _trainer, _training_active

    if not _trainer:
        return {"active": False, "message": "No training has been started."}

    summary = _trainer.get_training_summary()
    return {
        "active":            _training_active,
        "total_episodes":    summary.get("total_episodes", 0),
        "best_reward":       summary.get("best_reward", None),
        "best_episode":      summary.get("best_episode", None),
        "avg_reward_last10": summary.get("avg_reward_last10", None),
        "epsilon":           _trainer.agent.epsilon if _trainer else None,
    }


@router.get("/history")
async def get_training_history():
    """Return full episode-by-episode training metrics."""
    global _trainer
    if not _trainer:
        raise HTTPException(status_code=400, detail="No training has been started.")
    return _trainer.get_training_summary()


@router.get("/models")
async def list_models():
    """List all saved model files and checkpoints."""
    return _model_manager.list_models()


@router.post("/load")
async def load_model(req: LoadModelRequest):
    """Load a saved model into the active agent (for inference)."""
    from .simulation_api import _agent
    global _trainer

    if not _trainer:
        raise HTTPException(status_code=400, detail="No agent initialized. Start training first.")

    try:
        _model_manager.load_inference_model(_trainer.agent, req.filename)
        return {"status": "loaded", "filename": req.filename}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

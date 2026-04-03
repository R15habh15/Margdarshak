"""
parallel_trainer.py
Runs multiple SUMO simulations in parallel and feeds transitions
into a shared DRLAgent replay buffer.

Key design decisions
--------------------
1. Each worker owns a RewardCalculator instance — rich 6-component
   reward replaces the old inline queue/wait formula.
2. Each worker receives its city's node_mask so it queries only
   real TL IDs from SUMO — eliminates "Traffic light not known" spam.
3. State matrices are always (N, STATE_DIM) where N = unified node count.
   Absent nodes are zero-padded by build_network_state().
4. Workers send None as a sentinel when done so the main process
   knows exactly when to stop draining the queue.
5. A per-item timeout prevents infinite blocking if a worker dies.
6. City selection uses a rotating shuffle — no duplicates per round,
   every city gets equal training exposure over time.
"""

import multiprocessing as mp
import random
import logging
import queue as queue_module
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------
# Worker  (runs in a child process)
# ---------------------------------------------------------------

def worker_process(
    config_path    : str,
    city_name      : str,
    agent,                        # DRLAgent (pickled to child)
    steps          : int,
    result_queue,                 # mp.Queue
    port           : int,
    node_mask      : np.ndarray,  # (N,) bool — which nodes exist here
    unified_tl_ids : List[str],   # full ordered node list
):
    from src.simulation.traffic_env import TrafficEnv
    from src.sensing.state_vector import build_network_state
    from src.brain.reward_calculator import RewardCalculator

    env = TrafficEnv(config_path=config_path, mode="ai")

    try:
        env.start(port=port)
    except Exception as e:
        logger.warning(f"[{city_name}:{port}] Failed to start env: {e}")
        result_queue.put(None)
        return

    # Validate — active TL IDs are those where mask is True
    active_tl_ids = [
        unified_tl_ids[i]
        for i in range(len(unified_tl_ids))
        if node_mask[i]
    ]

    if not active_tl_ids:
        logger.warning(f"[{city_name}:{port}] No active TL IDs — skipping.")
        env.stop()
        result_queue.put(None)
        return

    # Cross-check with what SUMO actually loaded for this map
    sumo_tl_ids = set(env.bridge.get_traffic_light_ids())
    matched     = [tid for tid in active_tl_ids if tid in sumo_tl_ids]

    if not matched:
        logger.warning(
            f"[{city_name}:{port}] No unified TL IDs matched SUMO — skipping."
        )
        env.stop()
        result_queue.put(None)
        return

    logger.info(
        f"[{city_name}:{port}] {len(matched)}/{len(unified_tl_ids)} "
        f"nodes active."
    )

    # ✅ One RewardCalculator per worker — maintains state across steps
    reward_calc = RewardCalculator()
    reward_calc.reset()

    collected = 0

    for _ in range(steps):
        try:
            # --- Observe state BEFORE action ---
            state_matrix, raw, _ = build_network_state(
                env.bridge,
                tl_order  = unified_tl_ids,
                node_mask = node_mask,
            )

            if state_matrix.shape != (len(unified_tl_ids), 8):
                continue

            # --- Select actions (active nodes only) ---
            actions = agent.select_actions(
                state_matrix,
                node_mask = node_mask,
            )

            # --- Apply actions and advance simulation ---
            env.step(actions)

            # --- Observe state AFTER action ---
            next_state_matrix, raw_next, _ = build_network_state(
                env.bridge,
                tl_order  = unified_tl_ids,
                node_mask = node_mask,
            )

            if next_state_matrix.shape != (len(unified_tl_ids), 8):
                continue

            # --- Gather reward inputs ---
            # Cumulative vehicles that completed their trip network-wide
            try:
                arrived_total = env.bridge.get_arrived_vehicle_count()
            except Exception:
                arrived_total = reward_calc._prev_arrived  # fallback: no delta

            # Current phase for each active TL
            current_phases = {}
            for tid in matched:
                try:
                    current_phases[tid] = env.bridge.get_tl_phase(tid)
                except Exception:
                    pass

            # ✅ Rich 6-component reward
            reward = reward_calc.scalar(
                raw_features   = raw_next,
                arrived_total  = arrived_total,
                current_phases = current_phases,
            )

            result_queue.put((
                state_matrix,
                actions,
                reward,
                next_state_matrix,
                False,
                node_mask,
            ))

            collected += 1

        except Exception as e:
            logger.warning(f"[{city_name}:{port}] Step error: {e}")
            continue

    env.stop()
    result_queue.put(None)   # sentinel
    logger.info(f"[{city_name}:{port}] Done — {collected} transitions.")


# ---------------------------------------------------------------
# Trainer
# ---------------------------------------------------------------

class ParallelSUMOTrainer:

    def __init__(
        self,
        agent,
        env_config       : Dict,
        num_envs         : int = 4,
        steps            : int = 300,
        train_iterations : int = 50,
    ):
        self.agent            = agent
        self.env_config       = env_config
        self.num_envs         = num_envs
        self.steps            = steps
        self.train_iterations = train_iterations

        # Rotating deck for diverse, no-duplicate city selection.
        self._city_deck: List[str] = []

    # -----------------------------------------------------------

    def _next_diverse_cities(self, available_paths: List[str]) -> List[str]:
        """
        Return num_envs paths with NO duplicates in the same round.

        Rotating-shuffle deck:
          - Pop num_envs items from the front each round.
          - Refill with a fresh shuffle when running low.
          Guarantees: no intra-round duplicates, all cities equally visited.
        """
        n = min(self.num_envs, len(available_paths))

        while len(self._city_deck) < n:
            fresh = available_paths.copy()
            random.shuffle(fresh)
            self._city_deck.extend(fresh)

        selected        = self._city_deck[:n]
        self._city_deck = self._city_deck[n:]

        return selected

    # -----------------------------------------------------------

    def train(self) -> bool:

        config_paths   = self.env_config.get("config_paths",   [])
        city_names     = self.env_config.get("city_names",     [])
        city_masks     = self.env_config.get("city_masks",     {})
        unified_tl_ids = self.env_config.get("unified_tl_ids", [])

        if not config_paths:
            logger.error("No config_paths provided.")
            return False

        # Build lookup: config_path -> (city_name, node_mask)
        city_lookup: Dict[str, tuple] = {}
        for name, path in zip(city_names, config_paths):
            mask = city_masks.get(name)
            if mask is not None:
                city_lookup[path] = (name, mask)

        if not city_lookup:
            logger.error("city_masks is empty — cannot route workers.")
            return False

        available_paths = list(city_lookup.keys())

        # ✅ Diverse, no-duplicate city selection for this round
        selected_paths = self._next_diverse_cities(available_paths)

        logger.info(
            f"[Trainer] This round: "
            f"{[city_lookup[p][0] for p in selected_paths]}"
        )

        result_queue = mp.Queue()
        processes    = []
        spawned      = 0

        for i, config_path in enumerate(selected_paths):

            city_name, node_mask = city_lookup[config_path]
            port                 = 8813 + i

            logger.info(f"[Trainer] Worker {i} → {city_name} on port {port}")

            p = mp.Process(
                target = worker_process,
                args   = (
                    config_path,
                    city_name,
                    self.agent,
                    self.steps,
                    result_queue,
                    port,
                    node_mask,
                    unified_tl_ids,
                ),
            )

            p.start()
            processes.append(p)
            spawned += 1

        # Drain queue until all workers send their sentinel
        experiences  = []
        workers_done = 0
        ITEM_TIMEOUT = 180

        while workers_done < spawned:
            try:
                item = result_queue.get(timeout=ITEM_TIMEOUT)

                if item is None:
                    workers_done += 1
                else:
                    experiences.append(item)

            except queue_module.Empty:
                logger.warning(
                    f"[Trainer] Queue timeout — "
                    f"{spawned - workers_done} worker(s) may have hung."
                )
                break

        for p in processes:
            p.join(timeout=15)
            if p.is_alive():
                logger.warning(
                    f"[Trainer] Force-terminating hung worker pid={p.pid}"
                )
                p.terminate()

        logger.info(
            f"[Trainer] Round complete — {len(experiences)} transitions collected."
        )

        for s, a, r, ns, d, mask in experiences:
            self.agent.store_transition(s, a, r, ns, d, mask)

        replay_size = len(self.agent.replay)

        if replay_size >= self.agent.batch_size:
            losses = []
            for _ in range(self.train_iterations):
                loss = self.agent.train_step()
                if loss is not None:
                    losses.append(loss)

            if losses:
                logger.info(
                    f"[Trainer] {len(losses)} train steps — "
                    f"avg loss: {sum(losses)/len(losses):.4f}  "
                    f"epsilon: {self.agent.epsilon:.3f}"
                )
        else:
            logger.info(
                f"[Trainer] Buffer {replay_size}/{self.agent.batch_size} — "
                f"skipping training this round."
            )

        return True
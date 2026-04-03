"""
train_ai.py
Entry point for multi-city unified-graph DRL training.

Flow
----
1. For every city config, spin up a temporary SUMO instance to
   retrieve the exact TL IDs that city's simulation exposes.
2. Filter out cities that have fewer than MIN_TL_COUNT signals —
   tiny maps produce weak, noisy gradients and hurt generalisation.
3. Build a UNIFIED graph (union of all remaining cities) via
   build_unified_graph().
4. Construct one DRLAgent with the unified node set.
5. Run ParallelSUMOTrainer in a loop — workers use per-city masks
   so they only query TL IDs that actually exist in their map, and
   the rotating-shuffle deck ensures no city repeats in a round.
"""

import os
import sys
import logging
import multiprocessing

import torch

# Suppress dynamo before any torch_geometric import (Windows spawn fix)
try:
    torch._dynamo.config.suppress_errors = True
except Exception:
    pass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

from src.brain.drl_agent import DRLAgent
from src.training.parallel_trainer import ParallelSUMOTrainer
from src.utils.graph_builder import build_unified_graph
from src.simulation.traci_bridge import TraCIBridge

logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(__file__))

# Cities with fewer than this many traffic lights are excluded.
# They produce weak gradients and skew learning toward trivial patterns.
MIN_TL_COUNT = 5

# Each entry: (display_name, filename_stem)
CITIES = [
    ("delhi",     "connaught_place_delhi_india"),
    ("mumbai",    "bandra_mumbai"),
    ("bangalore", "indiranagar_bangalore"),
    ("hyderabad", "hitech_city_hyderabad"),
    ("chennai",   "t_nagar_chennai"),
    ("kolkata",   "salt_lake_kolkata"),
    ("pune",      "shivajinagar_pune"),
    ("ahmedabad", "sg_highway_ahmedabad"),
    ("jaipur",    "mi_road_jaipur"),
    ("lucknow",   "hazratganj_lucknow"),
]


def make_paths(filename: str) -> dict:
    return {
        "config" : os.path.join(BASE_DIR, "data", "configs",      f"{filename}.sumocfg"),
        "net"    : os.path.join(BASE_DIR, "data", "sumo_networks", f"{filename}.net.xml"),
    }


# ---------------------------------------------------------------
# City probing
# ---------------------------------------------------------------

def get_tl_ids_for_city(config_path: str, port: int) -> list:
    """
    Start SUMO briefly on `port` to discover which TL IDs are live.
    Returns a sorted list; empty list on any failure.
    """
    bridge = TraCIBridge()
    try:
        bridge.start(config_path, port=port)
        ids = sorted(bridge.get_traffic_light_ids())
    except Exception as e:
        logger.warning(f"Could not probe {config_path}: {e}")
        ids = []
    finally:
        try:
            bridge.stop()
        except Exception:
            pass
    return ids


def probe_all_cities(cities: list, base_port: int = 8800) -> list:
    """
    Sequentially probe each city, filter weak maps, and return a list
    of dicts ready for build_unified_graph().

    Filtering rules (applied in order):
      1. Config / net XML file must exist on disk.
      2. SUMO must expose at least one TL (no empty maps).
      3. City must have >= MIN_TL_COUNT traffic lights.
         Maps below this threshold produce noisy, low-signal gradients.
    """
    city_configs = []
    skipped      = []

    for i, (city_name, filename) in enumerate(cities):
        paths = make_paths(filename)

        if not os.path.exists(paths["config"]):
            logger.warning(f"[{city_name}] Config not found — skipping.")
            skipped.append((city_name, "missing config"))
            continue

        if not os.path.exists(paths["net"]):
            logger.warning(f"[{city_name}] Net XML not found — skipping.")
            skipped.append((city_name, "missing net.xml"))
            continue

        port   = base_port + i
        tl_ids = get_tl_ids_for_city(paths["config"], port=port)

        if not tl_ids:
            logger.warning(f"[{city_name}] No traffic lights — skipping.")
            skipped.append((city_name, "0 TL IDs"))
            continue

        # ✅ Filter: skip cities that are too small to train meaningfully
        if len(tl_ids) < MIN_TL_COUNT:
            logger.warning(
                f"[{city_name}] Only {len(tl_ids)} TL(s) — below "
                f"MIN_TL_COUNT={MIN_TL_COUNT}. Skipping (weak training signal)."
            )
            skipped.append((city_name, f"only {len(tl_ids)} TLs < {MIN_TL_COUNT}"))
            continue

        city_configs.append({
            "city_name" : city_name,
            "net_path"  : paths["net"],
            "tl_ids"    : tl_ids,
            "config"    : paths["config"],
        })

        logger.info(f"[{city_name}] ✅ Accepted — {len(tl_ids)} TL IDs.")

    # Summary table
    logger.info("\n" + "─" * 55)
    logger.info(f"  Cities accepted : {len(city_configs)}")
    if skipped:
        logger.info(f"  Cities skipped  : {len(skipped)}")
        for name, reason in skipped:
            logger.info(f"    • {name:<12}  ({reason})")
    logger.info("─" * 55 + "\n")

    return city_configs


# ---------------------------------------------------------------
# Main
# ---------------------------------------------------------------

def main():

    logger.info("=" * 60)
    logger.info("  Margadarshak — Multi-City Unified GNN Training")
    logger.info("=" * 60)

    # Step 1 — probe and filter cities
    logger.info("\n[Setup] Probing cities for traffic light IDs...\n")

    city_configs = probe_all_cities(CITIES, base_port=8800)

    if not city_configs:
        logger.error("No valid cities found after filtering. Aborting.")
        return

    accepted_names = [c["city_name"] for c in city_configs]
    tl_counts      = {c["city_name"]: len(c["tl_ids"]) for c in city_configs}

    logger.info(
        f"[Setup] Training on {len(city_configs)} cities: {accepted_names}"
    )
    for name, count in tl_counts.items():
        logger.info(f"  {name:<14} {count} TLs")

    # Step 2 — build unified graph
    logger.info("\n[Setup] Building unified multi-city graph...\n")

    unified = build_unified_graph(city_configs, max_hops=20)

    logger.info(
        f"\n[Setup] Unified graph: {unified['num_nodes']} nodes, "
        f"{unified['edge_index'].shape[1]} edges\n"
    )

    # Step 3 — construct agent
    agent = DRLAgent(
        tl_ids     = unified["unified_tl_ids"],
        edge_index = unified["edge_index"],
    )

    # Step 4 — build env_config for trainer
    env_config = {
        "config_paths"   : [c["config"]    for c in city_configs],
        "city_names"     : [c["city_name"] for c in city_configs],
        "city_masks"     : unified["city_masks"],
        "unified_tl_ids" : unified["unified_tl_ids"],
        "mode"           : "ai",
    }

    trainer = ParallelSUMOTrainer(
        agent             = agent,
        env_config        = env_config,
        num_envs          = min(4, len(city_configs)),
        steps             = 300,
        train_iterations  = 50,
    )

    # Step 5 — training loop
    print("\n🚀 Starting unified multi-city training...\n")

    round_num = 0

    try:
        while True:
            round_num += 1
            logger.info(f"\n{'─'*50}  Round {round_num}  {'─'*50}\n")

            trainer.train()
            agent.save()

    except KeyboardInterrupt:
        agent.save()
        print(f"\n⛔ Training stopped after {round_num} rounds — model saved.")


# ---------------------------------------------------------------

if __name__ == "__main__":
    multiprocessing.freeze_support()   # Windows spawn fix
    main()
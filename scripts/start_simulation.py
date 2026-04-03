"""
start_simulation.py
CLI helper to launch and run a SUMO simulation directly from the terminal.

Modes:
  static       — Fixed-timer signal cycling (baseline)
  ai           — GNN + DRL agent controls signals
  backpressure — Backpressure algorithm controls signals

Usage:
    python scripts/start_simulation.py --config delhi.sumocfg --mode static
    python scripts/start_simulation.py --config delhi.sumocfg --mode ai --model rl_policy.pt
    python scripts/start_simulation.py --config delhi.sumocfg --mode static --gui
    python scripts/start_simulation.py --list
"""

import sys
import os
import argparse
import logging
import time
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../backend"))

from src.simulation.traffic_env import TrafficEnv
from src.simulation.signal_controller import SignalMode
from src.osm_pipeline.traffic_generator import list_configs
from src.sensing.state_vector import build_network_state
from src.brain.backpressure import backpressure_actions

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
logger = logging.getLogger(__name__)

CONFIGS_DIR = os.path.join(os.path.dirname(__file__), "../data/configs")
MODELS_DIR  = os.path.join(os.path.dirname(__file__), "../backend/models")


# ------------------------------------------------------------
# CLI Arguments
# ------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(description="Run a Margadarshak traffic simulation.")

    parser.add_argument("--config", type=str,
                        help="SUMO config filename (e.g. delhi.sumocfg)")

    parser.add_argument("--mode", type=str, default="static",
                        choices=["static", "ai", "backpressure"],
                        help="Signal control mode (default: static)")

    parser.add_argument("--model", type=str, default="rl_policy.pt",
                        help="Model filename for AI mode (default: rl_policy.pt)")

    parser.add_argument("--max-steps", type=int, default=3600,
                        help="Maximum simulation steps")

    parser.add_argument("--port", type=int, default=8813,
                        help="TraCI port")

    parser.add_argument("--gui", action="store_true",
                        help="Open SUMO GUI")

    parser.add_argument("--print-every", type=int, default=300,
                        help="Print statistics every N steps")

    parser.add_argument("--list", action="store_true",
                        help="List available simulation configs")
    parser.add_argument(
        "--train",
        action="store_true",
        help="Enable training during simulation"
        )

    return parser.parse_args()


# ------------------------------------------------------------
# AI Loader
# ------------------------------------------------------------

def load_ai_agent(config_path: str, port: int, model_filename: str):

    from src.simulation.traci_bridge import TraCIBridge
    from src.utils.graph_builder import load_sumo_network, build_tl_graph
    from src.brain.drl_agent import DRLAgent
    from src.brain.model_manager import ModelManager

    logger.info("Preparing AI graph...")

    # ---------------------------------------
    # Extract SUMO network path
    # ---------------------------------------

    with open(config_path) as f:
        content = f.read()

    match = re.search(r'<net-file value="([^"]+)"', content)

    if not match:
        raise ValueError("Could not find net-file in sumocfg")

    net_path = match.group(1)

    # ---------------------------------------
    # Temporary TraCI connection
    # ---------------------------------------

    bridge = TraCIBridge()
    bridge.start(config_path, port=port)

    tl_ids = sorted(bridge.get_traffic_light_ids())

    bridge.stop()
    time.sleep(0.5)

    # ---------------------------------------
    # Build graph
    # ---------------------------------------

    net = load_sumo_network(net_path)

    _, edge_index, _ = build_tl_graph(net, tl_ids)

    # ---------------------------------------
    # Initialize DRL agent
    # ---------------------------------------

    agent = DRLAgent(
        tl_ids=tl_ids,
        edge_index=edge_index
    )

    manager = ModelManager()

    loaded = manager.load_inference_model(agent, model_filename)

    if not loaded:
        logger.warning("No trained model found — creating new DRL policy.")
        manager.save_inference_model(agent, model_filename)

    logger.info(f"AI controlling {len(tl_ids)} intersections.")

    return agent


# ------------------------------------------------------------
# Console Statistics
# ------------------------------------------------------------

def print_stats(step: int, state: dict, total_wait: float):

    tl_data = state.get("traffic_lights", {})

    total_queue = sum(
        sum(l["queue_length"] for l in tl["lanes"].values())
        for tl in tl_data.values()
    )

    print(
        f"  Step {step:5d} | "
        f"Vehicles: {state['active_vehicles']:4d} | "
        f"Queue: {total_queue:5.0f} | "
        f"Wait: {total_wait:8.1f}s | "
        f"Arrived: {state.get('arrived', 0):4d}"
    )


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():

    args = parse_args()

    if args.list:
        print("\n=== Available Simulation Configs ===")

        configs = list_configs()

        for f in (configs or ["(none — run generate_routes.py first)"]):
            print(f"  {f}")

        return

    if not args.config:
        print("Error: --config is required.")
        sys.exit(1)

    config_path = os.path.join(CONFIGS_DIR, args.config)

    if not os.path.exists(config_path):
        print(f"Error: Config not found: {config_path}")
        sys.exit(1)

    mode = SignalMode.AI if args.mode in ("ai", "backpressure") else SignalMode.STATIC

    agent = None

    # --------------------------------------------------------
    # AI Initialization
    # --------------------------------------------------------

    if args.mode == "ai":

        logger.info("Initializing DRL agent...")

        agent = load_ai_agent(config_path, args.port, args.model)

        logger.info("DRL agent ready.")

    # --------------------------------------------------------
    # Simulation Header
    # --------------------------------------------------------

    print(f"\n{'='*60}")
    print("  Margadarshak Simulation")
    print(f"  Config : {args.config}")
    print(f"  Mode   : {args.mode.upper()}")
    print(f"  Steps  : {args.max_steps}")
    print(f"{'='*60}\n")

    env = TrafficEnv(
        config_path=config_path,
        mode=mode,
        use_gui=args.gui
    )

    env.start(port=args.port)

    total_wait = 0.0
    step = 0
    start_time = time.time()

    try:

        while not env.is_done() and step < args.max_steps:

            ai_actions = None

            # ---------------------------------------
            # AI Mode
            # ---------------------------------------

            if args.mode == "ai" and agent:

                # Current state
                state_matrix, raw_features, _ = build_network_state(
                    env.bridge,
                    tl_order=agent.tl_ids
                )

                # Select actions
                actions = agent.select_actions(state_matrix)

                # Apply actions
                state = env.step(ai_actions=actions)

                # Next state
                next_state_matrix, next_raw_features, _ = build_network_state(
                    env.bridge,
                    tl_order=agent.tl_ids
                )

                # Compute reward
                reward = agent.compute_reward(next_raw_features)
                if args.train:
                    # Store experience
                    agent.store_transition(
                        state_matrix,
                        actions,
                        reward,
                        next_state_matrix,
                        done=env.is_done()
                    )

                    # Train periodically
                    if step % 5 == 0:
                        loss = agent.train_step()

                        if loss:
                            logger.info(f"Training loss: {loss:.4f}")

                ai_actions = actions

            # ---------------------------------------
            # Backpressure Mode
            # ---------------------------------------

            elif args.mode == "backpressure":

                ai_actions = backpressure_actions(env.bridge)

                state = env.step(ai_actions=ai_actions)

            # ---------------------------------------
            # Static Mode
            # ---------------------------------------

            else:

                state = env.step()

            # ---------------------------------------
            # Metrics
            # ---------------------------------------

            tl_data = state.get("traffic_lights", {})

            total_wait += sum(
                sum(l["waiting_time"] for l in tl["lanes"].values())
                for tl in tl_data.values()
            )

            step += 1

            if step % args.print_every == 0:
                print_stats(step, state, total_wait)

            # Save model periodically
            if args.mode == "ai" and step % 1000 == 0:
                agent.save()
    except KeyboardInterrupt:

        print("\nInterrupted by user.")

    finally:

        summary = env.get_metrics_summary()

        elapsed = time.time() - start_time

        env.stop()

    # --------------------------------------------------------
    # Final Summary
    # --------------------------------------------------------

    print(f"\n{'='*60}")
    print("  SIMULATION COMPLETE")
    print(f"{'='*60}")
    print(f"  Mode              : {args.mode.upper()}")
    print(f"  Total Steps       : {summary['total_steps']}")
    print(f"  Vehicles Departed : {summary['total_departed']}")
    print(f"  Vehicles Arrived  : {summary['total_arrived']}")
    print(f"  Total Wait Time   : {summary['total_waiting_time']:.1f}s")
    print(f"  Avg Wait / Step   : {summary['avg_waiting_time_per_step']:.4f}s")
    print(f"  Wall Clock Time   : {elapsed:.1f}s")
    print(f"{'='*60}\n")


# ------------------------------------------------------------

if __name__ == "__main__":
    main()
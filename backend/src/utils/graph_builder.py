"""
graph_builder.py
Builds traffic-light graph for GNN learning.

Supports:
  - Single-city graph  : build_tl_graph()
  - Unified multi-city : build_unified_graph()

The unified graph unions ALL TL IDs across every city into one
fixed node set. Each city receives a boolean node_mask that marks
which nodes are active in its simulation. Absent nodes get
zero-padded features and are excluded from the training loss.
"""

import os
import logging
import numpy as np
import sumolib
from typing import List, Tuple, Dict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------
# Load SUMO Network
# ---------------------------------------------------------------

def load_sumo_network(net_path: str) -> sumolib.net.Net:

    if not os.path.exists(net_path):
        raise FileNotFoundError(f"SUMO network not found: {net_path}")

    logger.info(f"Loading SUMO network: {net_path}")

    return sumolib.net.readNet(net_path)


# ---------------------------------------------------------------
# Single-City Graph  (original API — unchanged)
# ---------------------------------------------------------------

def build_tl_graph(
    net: sumolib.net.Net,
    tl_ids: List[str],
    max_hops: int = 20,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, int]]:
    """
    Build a graph for a single city.

    Returns
    -------
    positions    : (N, 2)  normalised node coordinates
    edge_index   : (2, E)  adjacency list
    tl_index_map : {tl_id -> node index}
    """

    tl_set       = set(tl_ids)
    sorted_ids   = sorted(tl_ids)
    tl_index_map = {tid: i for i, tid in enumerate(sorted_ids)}
    N            = len(sorted_ids)

    # Node positions
    positions   = np.zeros((N, 2), dtype=np.float32)
    valid_nodes = {}

    for tid in sorted_ids:
        try:
            valid_nodes[tid] = net.getNode(tid)
        except KeyError:
            logger.warning(f"Skipping missing traffic light node: {tid}")

    for tid, node in valid_nodes.items():
        idx        = tl_index_map[tid]
        x, y       = node.getCoord()
        positions[idx] = [x, y]

    if N > 1:
        lo  = positions.min(axis=0)
        hi  = positions.max(axis=0)
        rng = hi - lo
        rng[rng == 0] = 1
        positions = (positions - lo) / rng

    # BFS edge construction
    src_list, dst_list = [], []

    for tl_id in sorted_ids:
        try:
            start_node = net.getNode(tl_id)
        except KeyError:
            continue

        visited = {start_node.getID()}
        queue   = [(start_node, 0)]

        while queue:
            node, depth = queue.pop(0)
            if depth > max_hops:
                continue

            for edge in node.getOutgoing():
                nxt = edge.getToNode()
                nid = nxt.getID()

                if nid in visited:
                    continue
                visited.add(nid)

                if nid in tl_set and nid != tl_id:
                    src_list.append(tl_index_map[tl_id])
                    dst_list.append(tl_index_map[nid])

                queue.append((nxt, depth + 1))

    if not src_list:
        logger.warning("No edges found in traffic graph — using self-loops.")
        edge_index = np.array([list(range(N)), list(range(N))], dtype=np.int64)
    else:
        edge_index = np.array([src_list, dst_list], dtype=np.int64)

    logger.info(f"Graph built — nodes: {N}  edges: {edge_index.shape[1]}")

    return positions, edge_index, tl_index_map


# ---------------------------------------------------------------
# Unified Multi-City Graph
# ---------------------------------------------------------------

def build_unified_graph(
    city_configs: List[Dict],
    max_hops: int = 20,
) -> Dict:
    """
    Build one graph that spans ALL cities together.

    Parameters
    ----------
    city_configs : list of dicts, each:
        {
            "city_name" : str,
            "net_path"  : str,        # absolute path to .net.xml
            "tl_ids"    : List[str],  # TL IDs active in this city
        }

    Returns
    -------
    dict with keys:
        unified_tl_ids  : List[str]                   global sorted node list
        unified_index   : Dict[str, int]               tl_id -> global index
        edge_index      : np.ndarray (2, E)            union of all city edges
        city_masks      : Dict[str, np.ndarray(N,)]   bool mask per city
        city_tl_ids     : Dict[str, List[str]]         active TL IDs per city
        num_nodes       : int
    """

    # Step 1 — union of every TL ID across all cities
    all_tl_ids = set()
    for cfg in city_configs:
        all_tl_ids.update(cfg["tl_ids"])

    unified_tl_ids = sorted(all_tl_ids)
    unified_index  = {tid: i for i, tid in enumerate(unified_tl_ids)}
    N              = len(unified_tl_ids)

    logger.info(
        f"Unified graph — {N} total nodes across {len(city_configs)} cities"
    )

    # Step 2 — union edge index via BFS in each city's net
    all_src, all_dst = [], []
    edge_set         = set()   # deduplication

    for cfg in city_configs:
        city_name = cfg["city_name"]
        net_path  = cfg["net_path"]
        tl_ids    = cfg["tl_ids"]
        tl_set    = set(tl_ids)

        try:
            net = load_sumo_network(net_path)
        except Exception as e:
            logger.warning(f"[{city_name}] Cannot load network ({e}) — skipping edges")
            continue

        city_edges_added = 0

        for tl_id in tl_ids:
            try:
                start_node = net.getNode(tl_id)
            except KeyError:
                continue

            visited = {start_node.getID()}
            queue   = [(start_node, 0)]

            while queue:
                node, depth = queue.pop(0)
                if depth > max_hops:
                    continue

                for edge in node.getOutgoing():
                    nxt = edge.getToNode()
                    nid = nxt.getID()

                    if nid in visited:
                        continue
                    visited.add(nid)

                    if nid in tl_set and nid != tl_id:
                        src  = unified_index[tl_id]
                        dst  = unified_index[nid]
                        pair = (src, dst)

                        if pair not in edge_set:
                            edge_set.add(pair)
                            all_src.append(src)
                            all_dst.append(dst)
                            city_edges_added += 1

                    queue.append((nxt, depth + 1))

        logger.info(f"[{city_name}] added {city_edges_added} unique edges")

    # Fallback: self-loops so GATConv never gets an empty edge_index
    if not all_src:
        logger.warning("Unified graph has no edges — adding self-loops as fallback.")
        all_src = list(range(N))
        all_dst = list(range(N))

    edge_index = np.array([all_src, all_dst], dtype=np.int64)

    logger.info(f"Unified graph — total edges: {edge_index.shape[1]}")

    # Step 3 — boolean mask and active-TL list per city
    city_masks  = {}
    city_tl_ids = {}

    for cfg in city_configs:
        city_name = cfg["city_name"]
        tl_ids    = cfg["tl_ids"]

        mask = np.zeros(N, dtype=bool)
        active_ids = []

        for tid in tl_ids:
            if tid in unified_index:
                mask[unified_index[tid]] = True
                active_ids.append(tid)

        city_masks[city_name]  = mask
        city_tl_ids[city_name] = active_ids

        logger.info(
            f"[{city_name}] mask — {mask.sum()}/{N} nodes active"
        )

    return {
        "unified_tl_ids" : unified_tl_ids,
        "unified_index"  : unified_index,
        "edge_index"     : edge_index,
        "city_masks"     : city_masks,
        "city_tl_ids"    : city_tl_ids,
        "num_nodes"      : N,
    }


# ---------------------------------------------------------------
# Torch helpers
# ---------------------------------------------------------------

def edge_index_to_torch(edge_index):
    import torch
    return torch.tensor(edge_index, dtype=torch.long)


def build_pyg_data(node_features, edge_index, node_positions=None):
    import torch
    from torch_geometric.data import Data

    x  = torch.tensor(node_features, dtype=torch.float)
    ei = torch.tensor(edge_index,    dtype=torch.long)

    data = Data(x=x, edge_index=ei)

    if node_positions is not None:
        data.pos = torch.tensor(node_positions, dtype=torch.float)

    return data
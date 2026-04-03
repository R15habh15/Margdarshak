"""
congestion_detector.py
Detects and classifies congestion levels across the road network.

Provides:
  - Per-junction congestion scoring
  - Network-wide congestion level (LOW / MEDIUM / HIGH / CRITICAL)
  - Congestion hotspot identification
  - Congestion propagation detection (upstream/downstream spread)

Used by:
  - Dashboard API for heatmap visualization
  - RL agent as auxiliary state information
  - Metrics module for congestion event counting
"""

import logging
import numpy as np
from enum import Enum
from typing import Dict, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class CongestionLevel(str, Enum):
    FREE_FLOW  = "free_flow"    # < 20% occupancy
    LIGHT      = "light"        # 20–40%
    MODERATE   = "moderate"     # 40–60%
    HEAVY      = "heavy"        # 60–80%
    CRITICAL   = "critical"     # > 80%


# Thresholds for occupancy-based classification
OCCUPANCY_THRESHOLDS = {
    CongestionLevel.FREE_FLOW: (0.0,  0.20),
    CongestionLevel.LIGHT:     (0.20, 0.40),
    CongestionLevel.MODERATE:  (0.40, 0.60),
    CongestionLevel.HEAVY:     (0.60, 0.80),
    CongestionLevel.CRITICAL:  (0.80, 1.01),
}

# Score mapping for numeric operations
CONGESTION_SCORES = {
    CongestionLevel.FREE_FLOW: 0,
    CongestionLevel.LIGHT:     1,
    CongestionLevel.MODERATE:  2,
    CongestionLevel.HEAVY:     3,
    CongestionLevel.CRITICAL:  4,
}


@dataclass
class JunctionCongestion:
    """Congestion summary for a single junction."""
    tl_id:             str
    congestion_score:  float          # 0.0 – 1.0
    level:             CongestionLevel
    total_vehicles:    int
    total_queue:       int
    avg_occupancy:     float
    avg_waiting:       float
    is_hotspot:        bool = False


def compute_junction_score(junction_features: dict) -> float:
    """
    Compute a 0–1 congestion score for a single junction.

    Score is a weighted combination of:
      - Average lane occupancy
      - Normalized queue length
      - Normalized waiting time
    """
    lanes = junction_features.get("lanes", {})
    if not lanes:
        return 0.0

    avg_occ   = sum(l["occupancy"]    for l in lanes.values()) / len(lanes) / 100.0
    avg_queue = min(junction_features["total_queue_length"] / 30.0, 1.0)
    avg_wait  = min(junction_features["total_waiting_time"] / 300.0, 1.0)

    # Weighted combination
    score = 0.40 * avg_occ + 0.35 * avg_queue + 0.25 * avg_wait
    return round(float(np.clip(score, 0.0, 1.0)), 4)


def classify_congestion(score: float) -> CongestionLevel:
    """Map a 0–1 congestion score to a CongestionLevel enum."""
    for level, (lo, hi) in OCCUPANCY_THRESHOLDS.items():
        if lo <= score < hi:
            return level
    return CongestionLevel.CRITICAL


def detect_network_congestion(
    raw_features: Dict[str, dict],
    hotspot_threshold: float = 0.65,
) -> Dict[str, object]:
    """
    Analyse congestion across the entire network.

    Args:
        raw_features:       Output of extract_all_junctions()
        hotspot_threshold:  Score above which a junction is a hotspot

    Returns:
        Dict with per-junction results, hotspots, and network-level summary
    """
    junction_results: Dict[str, JunctionCongestion] = {}
    scores = []

    for tl_id, features in raw_features.items():
        lanes      = features.get("lanes", {})
        avg_occ    = (sum(l["occupancy"]    for l in lanes.values()) / len(lanes)) if lanes else 0.0
        avg_wait   = (sum(l["waiting_time"] for l in lanes.values()) / len(lanes)) if lanes else 0.0

        score  = compute_junction_score(features)
        level  = classify_congestion(score)
        scores.append(score)

        junction_results[tl_id] = JunctionCongestion(
            tl_id            = tl_id,
            congestion_score = score,
            level            = level,
            total_vehicles   = features["total_vehicles"],
            total_queue      = features["total_queue_length"],
            avg_occupancy    = round(avg_occ, 2),
            avg_waiting      = round(avg_wait, 2),
            is_hotspot       = score >= hotspot_threshold,
        )

    # Network-level summary
    network_score   = float(np.mean(scores)) if scores else 0.0
    network_level   = classify_congestion(network_score)
    hotspots        = [jc.tl_id for jc in junction_results.values() if jc.is_hotspot]
    critical_count  = sum(1 for jc in junction_results.values() if jc.level == CongestionLevel.CRITICAL)

    return {
        "network_score":    round(network_score, 4),
        "network_level":    network_level,
        "hotspots":         hotspots,
        "critical_count":   critical_count,
        "junction_count":   len(junction_results),
        "junctions": {
            tl_id: {
                "score":          jc.congestion_score,
                "level":          jc.level,
                "total_vehicles": jc.total_vehicles,
                "total_queue":    jc.total_queue,
                "avg_occupancy":  jc.avg_occupancy,
                "avg_waiting":    jc.avg_waiting,
                "is_hotspot":     jc.is_hotspot,
            }
            for tl_id, jc in junction_results.items()
        },
    }


def detect_propagation(
    congestion_history: List[Dict[str, float]],
    tl_id: str,
    window: int = 5,
) -> str:
    """
    Detect whether congestion at a junction is spreading, stable, or clearing.

    Args:
        congestion_history: List of past network congestion dicts (score per tl_id)
        tl_id:              Junction to analyse
        window:             Number of historical steps to examine

    Returns:
        "spreading" | "stable" | "clearing" | "unknown"
    """
    if len(congestion_history) < window:
        return "unknown"

    recent = [
        h["junctions"].get(tl_id, {}).get("score", 0.0)
        for h in congestion_history[-window:]
        if "junctions" in h
    ]

    if len(recent) < 2:
        return "unknown"

    delta = recent[-1] - recent[0]
    if delta > 0.10:
        return "spreading"
    elif delta < -0.10:
        return "clearing"
    else:
        return "stable"

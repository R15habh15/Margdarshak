"""
test_sensing.py
Unit tests for the sensing layer — state vector and congestion detection.
"""

import os
import sys
import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.sensing.state_vector import build_state_vector, get_state_dim, STATE_DIM
from src.sensing.congestion_detector import (
    compute_junction_score,
    classify_congestion,
    detect_network_congestion,
    CongestionLevel,
)


# ----------------------------------------------------------------
# State Vector
# ----------------------------------------------------------------

class TestStateVector:

    def _make_features(self, vehicles=10, queue=5, wait=30.0, speed=8.0, pressure=2):
        return {
            "tl_id":              "tl_test",
            "current_phase":      1,
            "total_vehicles":     vehicles,
            "total_queue_length": queue,
            "total_waiting_time": wait,
            "avg_speed":          speed,
            "pressure":           pressure,
            "lanes": {
                "lane_0": {"occupancy": 25.0, "vehicle_count": 5,  "waiting_time": 15.0, "mean_speed": 8.0, "queue_length": 3},
                "lane_1": {"occupancy": 15.0, "vehicle_count": 5,  "waiting_time": 15.0, "mean_speed": 8.0, "queue_length": 2},
            },
        }

    def test_state_vector_shape(self):
        features = self._make_features()
        vec = build_state_vector(features)
        assert vec.shape == (STATE_DIM,)
        assert STATE_DIM == 8

    def test_state_vector_dtype(self):
        features = self._make_features()
        vec = build_state_vector(features)
        assert vec.dtype == np.float32

    def test_state_vector_values_in_range(self):
        features = self._make_features()
        vec = build_state_vector(features)
        # All values except pressure should be in [-1, 1]
        assert np.all(vec >= -1.0)
        assert np.all(vec <= 1.0)

    def test_state_vector_zero_vehicles(self):
        features = self._make_features(vehicles=0, queue=0, wait=0, speed=0, pressure=0)
        vec = build_state_vector(features)
        assert vec[0] == 0.0   # norm_vehicle_count
        assert vec[1] == 0.0   # norm_queue

    def test_state_vector_max_clamp(self):
        # Values above max should clamp to 1.0
        features = self._make_features(vehicles=999, queue=999, wait=9999)
        vec = build_state_vector(features)
        assert vec[0] == pytest.approx(1.0)
        assert vec[1] == pytest.approx(1.0)
        assert vec[2] == pytest.approx(1.0)

    def test_phase_encoding_cyclic(self):
        # Phase 0 and phase N should produce different encodings
        f0 = self._make_features()
        f0["current_phase"] = 0
        f1 = self._make_features()
        f1["current_phase"] = 2
        v0 = build_state_vector(f0)
        v1 = build_state_vector(f1)
        assert not np.allclose(v0[6:], v1[6:])

    def test_get_state_dim(self):
        assert get_state_dim() == 8


# ----------------------------------------------------------------
# Congestion Detector
# ----------------------------------------------------------------

class TestCongestionDetector:

    def _make_junction(self, vehicles=5, queue=3, wait=20.0, occupancy=15.0):
        return {
            "tl_id":              "tl_test",
            "total_vehicles":     vehicles,
            "total_queue_length": queue,
            "total_waiting_time": wait,
            "avg_speed":          5.0,
            "pressure":           1,
            "lanes": {
                "lane_0": {"occupancy": occupancy, "vehicle_count": vehicles,
                           "waiting_time": wait, "mean_speed": 5.0, "queue_length": queue},
            },
        }

    def test_score_range(self):
        jf    = self._make_junction()
        score = compute_junction_score(jf)
        assert 0.0 <= score <= 1.0

    def test_free_flow_classification(self):
        jf    = self._make_junction(vehicles=1, queue=0, wait=0.0, occupancy=5.0)
        score = compute_junction_score(jf)
        level = classify_congestion(score)
        assert level == CongestionLevel.FREE_FLOW

    def test_critical_classification(self):
        jf    = self._make_junction(vehicles=45, queue=28, wait=290.0, occupancy=95.0)
        score = compute_junction_score(jf)
        level = classify_congestion(score)
        assert level in (CongestionLevel.HEAVY, CongestionLevel.CRITICAL)

    def test_detect_network_congestion_structure(self):
        raw_features = {
            "tl_A": self._make_junction(vehicles=10, queue=5, wait=30.0, occupancy=25.0),
            "tl_B": self._make_junction(vehicles=2,  queue=1, wait=5.0,  occupancy=8.0),
        }
        result = detect_network_congestion(raw_features)
        assert "network_score"  in result
        assert "network_level"  in result
        assert "hotspots"       in result
        assert "junctions"      in result
        assert "tl_A"           in result["junctions"]
        assert "tl_B"           in result["junctions"]

    def test_hotspot_detection(self):
        raw_features = {
            "tl_A": self._make_junction(vehicles=45, queue=28, wait=290.0, occupancy=95.0),
            "tl_B": self._make_junction(vehicles=1,  queue=0,  wait=0.0,   occupancy=5.0),
        }
        result = detect_network_congestion(raw_features, hotspot_threshold=0.5)
        assert "tl_A" in result["hotspots"]
        assert "tl_B" not in result["hotspots"]

    def test_empty_network(self):
        result = detect_network_congestion({})
        assert result["network_score"]  == 0.0
        assert result["junction_count"] == 0

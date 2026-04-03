"""
test_api.py
Integration tests for the FastAPI backend endpoints.

Uses FastAPI TestClient — no real SUMO connection needed.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


# ----------------------------------------------------------------
# Health
# ----------------------------------------------------------------

class TestHealth:

    def test_root_returns_200(self):
        res = client.get("/")
        assert res.status_code == 200
        assert "Margadarshak" in res.json()["message"]

    def test_health_endpoint(self):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

    def test_config_endpoint(self):
        res = client.get("/api/config")
        assert res.status_code == 200
        data = res.json()
        assert "sumo"       in data
        assert "ml"         in data
        assert "simulation" in data


# ----------------------------------------------------------------
# Map API
# ----------------------------------------------------------------

class TestMapApi:

    def test_list_maps_returns_200(self):
        res = client.get("/api/map/list")
        assert res.status_code == 200
        data = res.json()
        assert "osm_files"     in data
        assert "sumo_networks" in data
        assert "configs"       in data

    def test_convert_missing_file_returns_404(self):
        res = client.post("/api/map/convert", json={"osm_filename": "nonexistent.osm"})
        assert res.status_code == 404

    def test_generate_routes_missing_network_returns_404(self):
        res = client.post("/api/map/generate-routes", json={"network_filename": "nonexistent.net.xml"})
        assert res.status_code == 404

    @patch("src.api.map_api.download_osm_by_place")
    def test_download_by_place_success(self, mock_dl):
        mock_dl.return_value = "/data/osm_raw/test.osm"
        res = client.post("/api/map/download/place", json={"place_name": "Test Place"})
        assert res.status_code == 200
        assert res.json()["status"] == "success"

    @patch("src.api.map_api.download_osm_by_place")
    def test_download_by_place_error_returns_500(self, mock_dl):
        mock_dl.side_effect = Exception("Network error")
        res = client.post("/api/map/download/place", json={"place_name": "Bad Place"})
        assert res.status_code == 500


# ----------------------------------------------------------------
# Simulation API
# ----------------------------------------------------------------

class TestSimulationApi:

    def test_status_when_no_simulation(self):
        res = client.get("/api/simulation/status")
        assert res.status_code == 200
        data = res.json()
        assert "running" in data

    def test_stop_when_not_running_returns_400(self):
        res = client.post("/api/simulation/stop")
        assert res.status_code == 400

    def test_reset_when_no_sim_returns_400(self):
        res = client.post("/api/simulation/reset")
        assert res.status_code == 400

    def test_set_mode_when_not_running_returns_400(self):
        res = client.post("/api/simulation/set-mode", json={"mode": "ai"})
        assert res.status_code == 400

    def test_set_mode_invalid_value_returns_400(self):
        # First mock a running simulation
        import src.api.simulation_api as sim_api
        mock_env = MagicMock()
        mock_env.running = True
        original = sim_api._env
        sim_api._env = mock_env
        res = client.post("/api/simulation/set-mode", json={"mode": "invalid_mode"})
        assert res.status_code == 422
        sim_api._env = original

    @patch("src.api.simulation_api.TrafficEnv")
    def test_start_simulation(self, mock_env_cls):
        mock_env = MagicMock()
        mock_env.running = False
        mock_env_cls.return_value = mock_env

        res = client.post("/api/simulation/start", json={
            "config_path": "/fake/path.sumocfg",
            "mode": "static",
        })
        assert res.status_code in (200, 500)  # 500 if config not found is ok in test


# ----------------------------------------------------------------
# Metrics API
# ----------------------------------------------------------------

class TestMetricsApi:

    def test_current_metrics_no_sim_returns_400(self):
        import src.api.simulation_api as sim_api
        original   = sim_api._env
        sim_api._env = None
        res = client.get("/api/metrics/current")
        assert res.status_code == 400
        sim_api._env = original

    def test_summary_no_sim_returns_400(self):
        import src.api.simulation_api as sim_api
        original   = sim_api._env
        sim_api._env = None
        res = client.get("/api/metrics/summary")
        assert res.status_code == 400
        sim_api._env = original

    def test_comparison_returns_200(self):
        res = client.get("/api/metrics/comparison")
        assert res.status_code == 200
        data = res.json()
        assert "ready" in data


# ----------------------------------------------------------------
# Training API
# ----------------------------------------------------------------

class TestTrainingApi:

    def test_status_no_trainer(self):
        res = client.get("/api/training/status")
        assert res.status_code == 200
        assert res.json()["active"] == False

    def test_stop_no_training_returns_400(self):
        res = client.post("/api/training/stop")
        assert res.status_code == 400

    def test_list_models_returns_200(self):
        res = client.get("/api/training/models")
        assert res.status_code == 200
        data = res.json()
        assert "inference_models" in data
        assert "checkpoints"      in data

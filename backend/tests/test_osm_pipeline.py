"""
test_osm_pipeline.py
Unit tests for the OSM download and SUMO conversion pipeline.

Tests are run without actual SUMO/OSM network calls by mocking
external dependencies.
"""

import os
import pytest
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.osm_pipeline.osm_downloader import list_downloaded_maps
from src.osm_pipeline.osm_to_sumo import list_sumo_networks
from src.osm_pipeline.traffic_generator import list_configs, _write_sumo_config


# ----------------------------------------------------------------
# osm_downloader
# ----------------------------------------------------------------

class TestOsmDownloader:

    def test_list_downloaded_maps_returns_list(self):
        result = list_downloaded_maps()
        assert isinstance(result, list)

    @patch("src.osm_pipeline.osm_downloader.ox")
    def test_download_by_place_calls_osmnx(self, mock_ox):
        mock_graph = MagicMock()
        mock_ox.graph_from_place.return_value = mock_graph
        mock_ox.save_graph_xml = MagicMock()

        from src.osm_pipeline.osm_downloader import download_osm_by_place
        with patch("builtins.open", MagicMock()):
            try:
                download_osm_by_place("Test Place, India")
            except Exception:
                pass

        mock_ox.graph_from_place.assert_called_once_with("Test Place, India", network_type="drive")

    @patch("src.osm_pipeline.osm_downloader.ox")
    def test_download_by_bbox_calls_osmnx(self, mock_ox):
        mock_ox.graph_from_bbox.return_value = MagicMock()
        mock_ox.save_graph_xml = MagicMock()

        from src.osm_pipeline.osm_downloader import download_osm_by_bbox
        try:
            download_osm_by_bbox(28.64, 28.61, 77.22, 77.20, name="test")
        except Exception:
            pass

        mock_ox.graph_from_bbox.assert_called_once()


# ----------------------------------------------------------------
# osm_to_sumo
# ----------------------------------------------------------------

class TestOsmToSumo:

    def test_list_sumo_networks_returns_list(self):
        result = list_sumo_networks()
        assert isinstance(result, list)

    def test_convert_raises_file_not_found(self):
        from src.osm_pipeline.osm_to_sumo import convert_osm_to_sumo
        with pytest.raises(FileNotFoundError):
            convert_osm_to_sumo("nonexistent_file.osm")


# ----------------------------------------------------------------
# traffic_generator
# ----------------------------------------------------------------

class TestTrafficGenerator:

    def test_list_configs_returns_list(self):
        result = list_configs()
        assert isinstance(result, list)

    def test_write_sumo_config_creates_file(self, tmp_path):
        config_path = str(tmp_path / "test.sumocfg")
        _write_sumo_config(
            config_path  = config_path,
            net_path     = "/fake/net.xml",
            route_path   = "/fake/routes.rou.xml",
            duration     = 3600,
        )
        assert os.path.exists(config_path)
        with open(config_path) as f:
            content = f.read()
        assert "<net-file" in content
        assert "<route-files" in content
        assert "3600" in content

    def test_generate_routes_raises_file_not_found(self):
        from src.osm_pipeline.traffic_generator import generate_routes
        with pytest.raises(FileNotFoundError):
            generate_routes("nonexistent.net.xml")

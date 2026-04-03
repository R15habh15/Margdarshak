"""
test_utils.py
Unit tests for utility functions.
"""

import os
import sys
import pytest
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.utils.helpers import (
    ensure_dir, save_json, load_json,
    timestamp_str, safe_divide, clamp,
    moving_average, flatten_dict,
)


class TestHelpers:

    def test_ensure_dir_creates_directory(self, tmp_path):
        new_dir = str(tmp_path / "new" / "nested" / "dir")
        result  = ensure_dir(new_dir)
        assert os.path.isdir(new_dir)
        assert result == new_dir

    def test_save_and_load_json(self, tmp_path):
        data     = {"key": "value", "num": 42, "list": [1, 2, 3]}
        filepath = str(tmp_path / "test.json")
        save_json(data, filepath)
        loaded = load_json(filepath)
        assert loaded == data

    def test_load_json_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_json("/nonexistent/path/file.json")

    def test_timestamp_str_format(self):
        ts = timestamp_str()
        assert len(ts) == 15        # YYYYmmdd_HHMMSS
        assert ts[8] == "_"

    def test_safe_divide_normal(self):
        assert safe_divide(10.0, 2.0) == pytest.approx(5.0)

    def test_safe_divide_by_zero(self):
        assert safe_divide(10.0, 0.0) == 0.0
        assert safe_divide(10.0, 0.0, default=99.0) == 99.0

    def test_clamp_within_range(self):
        assert clamp(5.0, 0.0, 10.0) == 5.0

    def test_clamp_below_min(self):
        assert clamp(-5.0, 0.0, 10.0) == 0.0

    def test_clamp_above_max(self):
        assert clamp(15.0, 0.0, 10.0) == 10.0

    def test_moving_average_basic(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = moving_average(values, window=3)
        assert len(result) == len(values)
        assert result[-1] == pytest.approx((3+4+5)/3)

    def test_moving_average_empty(self):
        assert moving_average([]) == []

    def test_moving_average_window_1(self):
        values = [1.0, 2.0, 3.0]
        result = moving_average(values, window=1)
        assert result == pytest.approx(values)

    def test_flatten_dict_basic(self):
        nested = {"a": {"b": 1, "c": 2}, "d": 3}
        flat   = flatten_dict(nested)
        assert flat == {"a.b": 1, "a.c": 2, "d": 3}

    def test_flatten_dict_deep(self):
        nested = {"x": {"y": {"z": 42}}}
        flat   = flatten_dict(nested)
        assert flat == {"x.y.z": 42}

    def test_flatten_dict_no_nesting(self):
        d    = {"a": 1, "b": 2}
        flat = flatten_dict(d)
        assert flat == d


class TestGraphBuilder:

    def test_edge_index_to_torch(self):
        import numpy as np
        import torch
        from src.utils.graph_builder import edge_index_to_torch
        ei     = np.array([[0,1],[1,2]], dtype=np.int64)
        tensor = edge_index_to_torch(ei)
        assert isinstance(tensor, torch.Tensor)
        assert tensor.dtype == torch.long
        assert tensor.shape == (2, 2)

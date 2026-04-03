"""
helpers.py
Utility helper functions used across the Margadarshak backend.
"""

import os
import json
import datetime
from typing import Dict, Any, List


def ensure_dir(path: str) -> str:
    """Ensure a directory exists."""
    os.makedirs(path, exist_ok=True)
    return path


def save_json(data: Dict[str, Any], filepath: str):
    """Save dictionary as JSON."""
    ensure_dir(os.path.dirname(filepath))
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)


def load_json(filepath: str) -> Dict[str, Any]:
    """Load JSON file."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(filepath)

    with open(filepath) as f:
        return json.load(f)


def timestamp_str() -> str:
    """Return timestamp in format YYYYmmdd_HHMMSS."""
    return datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def safe_divide(a: float, b: float, default: float = 0.0) -> float:
    """Safe division handling divide-by-zero."""
    if b == 0:
        return default
    return a / b


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value within a range."""
    return max(min_val, min(value, max_val))


def moving_average(values: List[float], window: int = 3) -> List[float]:
    """Compute moving average."""
    if not values:
        return []

    result = []

    for i in range(len(values)):
        start = max(0, i - window + 1)
        subset = values[start:i + 1]
        result.append(sum(subset) / len(subset))

    return result


def flatten_dict(d: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    """Flatten nested dictionaries."""
    items = {}

    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k

        if isinstance(v, dict):
            items.update(flatten_dict(v, new_key, sep))
        else:
            items[new_key] = v

    return items
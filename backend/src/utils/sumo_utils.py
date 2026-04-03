import os

# Default SUMO installation path (Windows)
DEFAULT_SUMO_HOME = r"C:\Program Files (x86)\Eclipse\Sumo"


def get_sumo_home():
    """Return SUMO_HOME directory."""
    return os.environ.get("SUMO_HOME", DEFAULT_SUMO_HOME)


def get_sumo_bin(tool: str):
    """
    Return full path to a SUMO binary.
    Example: netconvert, duarouter, sumo, sumo-gui
    """
    sumo_home = get_sumo_home()
    path = os.path.join(sumo_home, "bin", f"{tool}.exe")

    if not os.path.exists(path):
        raise FileNotFoundError(f"{tool} not found at {path}")

    return path


def get_random_trips():
    """
    Return path to randomTrips.py
    """
    sumo_home = get_sumo_home()
    path = os.path.join(sumo_home, "tools", "randomTrips.py")

    if not os.path.exists(path):
        raise FileNotFoundError(f"randomTrips.py not found at {path}")

    return path
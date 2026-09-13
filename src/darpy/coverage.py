"""Lazy access to the legacy grid coverage planner.

Importing this module does not load NumPy, Numba, OpenCV, or pygame. The
scientific dependencies are loaded when a planner class is first requested.
This facade preserves the existing planner's public class names.
"""

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from darp import DARP
    from kruskal import Kruskal
    from multiRobotPathPlanner import MultiRobotPathPlanner, get_area_indices, get_area_map

__all__ = ["DARP", "MultiRobotPathPlanner", "Kruskal", "get_area_map", "get_area_indices"]

_MODULES = {
    "DARP": "darp",
    "MultiRobotPathPlanner": "multiRobotPathPlanner",
    "Kruskal": "kruskal",
    "get_area_map": "multiRobotPathPlanner",
    "get_area_indices": "multiRobotPathPlanner",
}


def __getattr__(name):
    if name not in _MODULES:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    try:
        value = getattr(import_module(_MODULES[name]), name)
    except ModuleNotFoundError as error:
        if error.name in {"numpy", "numba", "cv2"}:
            raise ImportError("Coverage planning requires the darpy[coverage] extra") from error
        raise
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))

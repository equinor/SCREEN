"""Basic user input well information, as validated by `WellModel`."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class WellRaw:
    """
    Basic user input well information
    Args:
    header (dict): well header
    hole_casings (list of dict): list of hole and casing information
    survey (dict of list): survey information
    plugs (list of dict): list of plug information
    stratigraphy (list of dict): list of stratigraphy information
    """

    header: Optional[Dict[str, Any]] = None
    hole_casings: Optional[List[Dict[str, Any]]] = None
    survey: Optional[Dict[str, List[float]]] = None
    plugs: Optional[List[Dict[str, Any]]] = None
    stratigraphy: Optional[List[Dict[str, Any]]] = None

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.WellClass.libs.well_class import Well
from src.WellClass.libs.well_class.well_validation import split_hole_casings
from src.WellClass.libs.well_computed.annulus import compute_annulus
from src.WellClass.libs.well_computed.borehole import compute_borehole
from src.WellClass.libs.well_computed.plug_properties import compute_plug_properties
from src.WellClass.libs.well_computed.plugs_diameter import compute_plugs_diameter


@dataclass
class WellProcessed(Well):
    borehole: Optional[List[Dict[str, Any]]] = None
    cement_bond: Optional[List[Dict[str, Any]]] = None
    annulus: Optional[List[Dict[str, Any]]] = None
    processed_plugs: Optional[List[Dict[str, Any]]] = None
    plug_names: Optional[List[str]] = None

    def __post_init__(self):
        # invoke parent post_init to compute wellpath and md2tvd
        super().__post_init__()
        self._compute_well()

    def _compute_well(self):
        splitted_hole_casing = split_hole_casings(self.hole_casings)

        casings = splitted_hole_casing["casing"]
        holes = splitted_hole_casing["holes"]
        cement_bond = splitted_hole_casing["casing_cement"]

        self.borehole = compute_borehole(holes, casings, self.md2tvd)
        self.cement_bond = compute_annulus(holes=holes, casings=casings, cement_bond=cement_bond, md2tvd=self.md2tvd, solve_cement_bond=True)
        self.annulus = compute_annulus(holes=holes, casings=casings, cement_bond=cement_bond, md2tvd=self.md2tvd)

        if self.inventory["plugs"]:
            self.processed_plugs = compute_plugs_diameter(self.plugs, self.borehole)
            self.plug_names = [plug["name"] for plug in self.plugs]

    def _compute_plug_properties(self, eval_plug: str):
        return compute_plug_properties(self.processed_plugs, self.plug_names, eval_plug)

# handle type hints problem for python version < 3.10
from typing import List, Optional, Union

from pydantic import BaseModel

from .well_model_utils import HoleCasingModel, PlugsModel, StratigraphyModel, SubsurfaceAssumptionsModel, WellHeaderModel, WellSurveyModel


class MetaDataModel(BaseModel):
    """meta data
    Args:
        namespace (str): name space
        name (str): can use it for project name
        author (str): who made this yaml file
    """

    namespace: str = "screen"
    name: Union[str, None] = None
    author: Union[str, None] = None


class WellSpec(BaseModel):
    """specs for standard well information
    Args:
        well_header (WellHeaderModel): well header information
        drilling (list[DrillingModel]): list of drilling information
        casing_cement (list[CasingCementModel]): list of casing information
        barrier (list[BarrierModel]):  list of barrier information
        barrier_permeability (BarrierPermeabilityModel): list of barrier permeability
        geology (list[GeologyModel]): list of geology, such as formations, information
        assumptions (AssumptionsModel): misceleaneous information
        co2_datum (CO2DatumModel): co2 datum
    """

    well_header: WellHeaderModel
    well_survey: Optional[WellSurveyModel] = None
    hole_casings: Optional[List[HoleCasingModel]] = None
    plugs: Optional[List[PlugsModel]] = None
    stratigraphy: Optional[List[StratigraphyModel]] = None


class WellModellingSpec(WellSpec):
    """extra specs for pressure information
    Args:
        reservoir_pressure (ReservoirPressureModel): general reservoir pressure information
        main_barrier (str): main barrier name to compute pressure
    """

    subsurface_assumptions: Optional[SubsurfaceAssumptionsModel] = None


class WellModel(BaseModel):
    """model including all parameters
    Args:
        apiVersion (str): current version of this yaml format
        kind (str): for GaP
        metadata (MetaDataModel): miscelaneous data
        spec (WellPressureSpec): well specification
    """

    apiVersion: str = "well/v0.1"
    kind: str = "Well"
    metadata: Optional[MetaDataModel] = None
    spec: WellModellingSpec

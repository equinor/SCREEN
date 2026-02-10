# handle type hints problem for python version < 3.10
from typing import List, Literal, Optional, Union

from pydantic import BaseModel, field_validator

from ..utils.fraction_float import fraction_float


class WellHeaderModel(BaseModel):
    """General information about the well.

    Args:
        well_name (str): well name
        well_rkb (float): RKB elevation
        sf_depth_msl (float): depth of the sea floor
        well_td_rkb (float): total depth of RKB
        sf_temp (float): sea floor temperature
        geo_tgrad  (float): geothermal gradient
    """

    unique_wellbore_identifier: str
    depth_reference_rkb: Union[int, float]
    depth_reference_rkb_unit: Literal["ft", "m"]
    ground_elevation: Union[int, float]
    ground_elevation_unit: Literal["ft", "m"]
    total_depth_rkb: Union[int, float]
    total_depth_rkb_unit: Literal["ft", "m"]


class WellSurveyModel(BaseModel):
    """Information about the well survey

    Args:
        md_rkb (float): measured depth in RKB
        inclination_deg (float): inclination in degree
        azimuth_deg (float): azimuth in degree
    """

    md_rkb: List[Union[int, float]]
    inclination_deg: List[Union[int, float]]
    azimuth_deg: List[Union[int, float]]


class HoleCasingModelRaw(BaseModel):
    """Information about the drilling intervals of the well

    Args:
        top_rkb (float): the top depth in RKB
        bottom_rkb (float): the bottom depth in RKB
        diameter_in (float, str): the diameter of the borehole in inches
    """

    name: str
    type: Literal["hole", "casing", "casing cement"]
    top_rkb: Union[int, float]
    bottom_rkb: Union[int, float]
    diameter_in: Union[float, int, str]
    shoe: Optional[bool] = False

    @field_validator("diameter_in")
    def diameter_in_converter(cls, v):
        if isinstance(v, (float, int)):
            return v
        elif isinstance(v, str):
            return fraction_float(v)
        else:
            raise ValueError("diameter_in must be a float or string")


class HoleCasingModel(HoleCasingModelRaw):
    """Information about the drilling intervals of the well

    Args:
        hc_perm (float): faked permeability for hole casing element
    """

    hc_perm: Optional[Union[int, float]] = None


class PlugsRaw(BaseModel):
    """Information about the barrier in the well

    Args:
        barrier_name (str): the barrier name
        barrier_type (str): the barrier type
        top_rkb (float): the top depth in RKB
        bottom_rkb (float): the bottom depth in RKB
        barrier_perm (float): permeability for the barrier
    """

    name: str
    type: Literal["cement", "mechanical plug"]
    top_rkb: Union[int, float]
    bottom_rkb: Union[int, float]


class PlugsModel(PlugsRaw):
    """Information about the barrier in the well

    Args:
        barrier_perm (float): permeability for the barrier
    """

    cement_perm: Optional[Union[int, float]] = None


class StratigraphyRaw(BaseModel):
    """The geological units encountered in the well

    Args:
        top_rkb (float): top depth in RKB
        geol_unit (str): name
        reservoir_flag (bool): whether or not it is considered a reservoir
    """

    name: str
    top_rkb: Union[int, float]
    bottom_rkb: Union[int, float]


class StratigraphyModel(StratigraphyRaw):
    """The geological units encountered in the well

    Args:
        reservoir_flag (bool): whether or not it is considered a reservoir
    """

    unit_type: Optional[str] = None
    unit_perm: Optional[Union[int, float]] = None


class ShminDataPoint(BaseModel):
    depth: float  # depth (e.g., meters)
    shmin: float  # minimum horizontal stress (e.g., MPa)


class SubsurfaceAssumptionsScenario(BaseModel):
    """model for subsurface assumptions"""

    temperature_gradient: Optional[Union[int, float]] = None
    ground_temperature: Optional[Union[int, float]] = None
    sg_brine: Optional[float] = None
    sg_fluid: Optional[float] = None
    fluid_type: Optional[str] = None
    shmin_gradient: Optional[float] = None
    shmin_data: Optional[List[ShminDataPoint]] = None
    salinity: Optional[Union[int, float]] = None
    z_fluid_contact: Optional[Union[int, float]] = None
    p_fluid_contact: Optional[Union[int, float]] = None
    z_resrv: Optional[Union[int, float]] = None
    p_resrv: Optional[Union[int, float]] = None
    z_msad: Optional[Union[int, float]] = None
    p_delta: Optional[Union[int, float]] = None


class SubsurfaceAssumptionsModel(BaseModel):
    """model for subsurface assumptions"""

    scenarios: Optional[List[SubsurfaceAssumptionsScenario]] = None

    @field_validator("scenarios", mode="before")
    def ensure_list(cls, v):
        if v is None:
            return v
        if isinstance(v, list):
            return v
        return [v]

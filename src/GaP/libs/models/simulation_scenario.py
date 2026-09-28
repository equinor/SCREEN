from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


class SimulationScenario(BaseModel):
    """GaP/CIRRUS inputs for one simulation case of a physical wellbore."""

    case_name: str = "default"
    temperature_gradient: float = 31.0
    ground_temperature: float = 4.0
    fluid_type: str = "co2"
    depth_unit: Literal["m"] = "m"
    pressure_unit: Literal["bar"] = "bar"
    z_fluid_contact: Optional[float] = Field(default=None, allow_inf_nan=False, description="Fluid-contact TVDMSL depth in m")
    p_fluid_contact: Optional[float] = Field(default=None, allow_inf_nan=False, description="Fluid-contact pressure in bar")
    overburden_datum_depth: Optional[float] = Field(default=None, allow_inf_nan=False, description="Overburden datum TVDMSL depth in m")
    z_resrv: Optional[float] = Field(default=None, allow_inf_nan=False, description="Reservoir TVDMSL depth in m")
    p_resrv: Optional[float] = Field(default=None, allow_inf_nan=False, description="Reservoir pressure in bar")
    salinity: float = 0.032

    @field_validator("case_name")
    @classmethod
    def case_name_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("case_name must not be blank")
        return value


class SimulationDesign(BaseModel):
    """Named simulation scenarios that share one immutable well description."""

    scenarios: list[SimulationScenario] = Field(default_factory=list)

    def select(self, case_name: str = "default") -> SimulationScenario:
        for scenario in self.scenarios:
            if scenario.case_name == case_name:
                return scenario
        available = ", ".join(scenario.case_name for scenario in self.scenarios) or "none"
        raise ValueError(f"unknown simulation case {case_name!r}; available cases: {available}")

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from .casing_hole import CasingHole


class SimulationScenario(BaseModel):
    """GaP/CIRRUS inputs for one simulation case of a physical wellbore."""

    case_name: str = "default"
    temperature_gradient: float = 31.0
    ground_temperature: float = 4.0
    fluid_type: str = "co2"
    depth_unit: Literal["m"] = "m"
    pressure_unit: Literal["bar"] = "bar"
    permeability_unit: Literal["mD"] = "mD"
    salinity_basis: Literal["mass_fraction"] = "mass_fraction"
    z_fluid_contact: Optional[float] = Field(default=None, allow_inf_nan=False, description="Fluid-contact TVDMSL depth in m")
    p_fluid_contact: Optional[float] = Field(default=None, allow_inf_nan=False, description="Fluid-contact pressure in bar")
    overburden_datum_depth: Optional[float] = Field(default=None, allow_inf_nan=False, description="Overburden datum TVDMSL depth in m")
    z_resrv: Optional[float] = Field(default=None, allow_inf_nan=False, description="Reservoir TVDMSL depth in m")
    p_resrv: Optional[float] = Field(default=None, allow_inf_nan=False, description="Reservoir pressure in bar")
    salinity: float = Field(default=0.032, ge=0, lt=1, allow_inf_nan=False, description="NaCl mass fraction of solution")
    reservoir_permx: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False, description="Reservoir PERMX override in mD")
    overburden_permx: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False, description="Overburden PERMX override in mD")
    cb_perm: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False, description="Casing-cement permeability override in mD")
    cb_perm_interval: str = Field(default="ALL", description="HoleCasings casing-cement name to override, or ALL")
    barrier_perm: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False, description="Plug-cement permeability override in mD")
    barrier_perm_interval: str = Field(default="ALL", description="Plugs name to override, or ALL")
    casing_hole_casing: Optional[str] = None
    casing_hole_depth_mTVDMSL: Optional[float] = Field(default=None, allow_inf_nan=False)
    casing_hole_diameter_m: Optional[float] = Field(default=None, gt=0, allow_inf_nan=False)

    @property
    def casing_hole(self) -> CasingHole | None:
        fields = (self.casing_hole_casing, self.casing_hole_depth_mTVDMSL, self.casing_hole_diameter_m)
        if all(value is None for value in fields):
            return None
        if self.casing_hole_casing is None or self.casing_hole_depth_mTVDMSL is None or self.casing_hole_diameter_m is None:
            raise ValueError("casing hole requires casing, depth_mTVDMSL, and diameter_m together")
        return CasingHole(
            casing=self.casing_hole_casing,
            depth_mTVDMSL=self.casing_hole_depth_mTVDMSL,
            diameter_m=self.casing_hole_diameter_m,
        )

    @model_validator(mode="after")
    def validate_casing_hole(self) -> SimulationScenario:
        self.casing_hole
        return self

    @field_validator("case_name")
    @classmethod
    def case_name_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("case_name must not be blank")
        return value

    @field_validator("cb_perm_interval", "barrier_perm_interval")
    @classmethod
    def interval_target_is_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("permeability interval target must not be blank; use ALL for every interval")
        return value.strip()

    @model_validator(mode="after")
    def interval_overrides_require_values(self) -> SimulationScenario:
        if self.cb_perm_interval != "ALL" and self.cb_perm is None:
            raise ValueError("cb_perm is required when cb_perm_interval targets a specific interval")
        if self.barrier_perm_interval != "ALL" and self.barrier_perm is None:
            raise ValueError("barrier_perm is required when barrier_perm_interval targets a specific interval")
        return self


class SimulationDesign(BaseModel):
    """Named simulation scenarios that share one immutable well description."""

    scenarios: list[SimulationScenario] = Field(default_factory=list)

    @model_validator(mode="after")
    def case_names_are_unique(self) -> SimulationDesign:
        names = [scenario.case_name for scenario in self.scenarios]
        duplicates = sorted({name for name in names if names.count(name) > 1})
        if duplicates:
            raise ValueError(f"case_name values must be unique; duplicated: {', '.join(duplicates)}")
        return self

    def select(self, case_name: str = "default") -> SimulationScenario:
        for scenario in self.scenarios:
            if scenario.case_name == case_name:
                return scenario
        available = ", ".join(scenario.case_name for scenario in self.scenarios) or "none"
        raise ValueError(f"unknown simulation case {case_name!r}; available cases: {available}")

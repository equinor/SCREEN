from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from ..pvt.pvt import default_pvt_path
from .pressure_scenario import PressureScenario
from .pressure_table import PressureTable

DEFAULT_TABLE_NAME = "default"


@dataclass
class Pressure:
    """
    Pressure scenarios for a well.

    Owns one or more named `PressureTable`s of well-level background curves
    (temperature, hydrostatic pressure, Shmin) - one per distinct set of
    geothermal/Shmin/brine-density assumptions, so sensitivities on those
    assumptions can be run side by side via `add_table`. Each `PressureScenario`,
    added via `add_scenario`, is anchored to one named table (the "default" table
    unless told otherwise). A "default" scenario anchored at `co2_datum` on the
    "default" table is created automatically.

    Args:
        header (dict): optional WellClass header. When supplied, its geometry values
            take precedence over the explicit geometry arguments below.
        ground_elevation (float): ground elevation (mMSL), required when `header`
            is not supplied.
        total_depth_rkb (float): total measured depth (mRKB), required when
            `header` is not supplied.
        depth_reference_rkb (float): RKB reference elevation (mMSL), required
            when `header` is not supplied.
        co2_datum (float): depth of the default CO2 scenario's fluid contact.
        pvt_path (str): directory where PVT files are located.
        fluid_type (str): named fluid to look up in the PVT collection for the
            variable-density integration (only "co2" is available today).
        ground_temperature (float): ground/seafloor temperature (degC).
        geothermal_gradient (float): geothermal gradient (degC/km).
        rho_brine (float): constant brine density (kg/m3) used for the hydrostatic
            pressure curve.
        shmin_gradient (float): linear Shmin gradient (bar/m) used when shmin_data
            is not provided.
        shmin_data (list): optional [[depth, Shmin], ...] control points.
        depth_step (float): depth sampling step (m) for every PressureTable.
    """

    header: Optional[dict] = None
    co2_datum: Optional[float] = None
    pvt_path: Optional[str] = None

    ground_elevation: Optional[float] = None
    total_depth_rkb: Optional[float] = None
    depth_reference_rkb: Optional[float] = None

    fluid_type: str = "co2"
    ground_temperature: float = None
    geothermal_gradient: float = None
    rho_brine: float = 1030.0
    shmin_gradient: Optional[float] = 0.1695
    shmin_data: Optional[List[List[float]]] = None
    depth_step: float = 10.0

    tables: dict = field(init=False, default_factory=dict)
    scenarios: dict = field(init=False, default_factory=dict)

    def __post_init__(self):
        self._resolve_geometry()
        if self.co2_datum is None:
            raise ValueError("co2_datum is required")
        if self.pvt_path is None:
            self.pvt_path = str(default_pvt_path())
        if self.ground_temperature is None or self.geothermal_gradient is None:
            raise ValueError("ground_temperature and geothermal_gradient are required to build the well's PressureTable")

        self.add_table(DEFAULT_TABLE_NAME)
        self.add_scenario("default", z_fluid_datum=self.co2_datum)

    @property
    def table(self) -> PressureTable:
        """The default PressureTable, kept for convenience when sensitivities aren't in play."""
        return self.tables[DEFAULT_TABLE_NAME]

    def _resolve_geometry(self) -> None:
        """Use a WellClass header when supplied, otherwise require explicit geometry."""
        if self.header is not None:
            self.ground_elevation = self.header["ground_elevation"]
            self.total_depth_rkb = self.header["total_depth_rkb"]
            self.depth_reference_rkb = self.header["depth_reference_rkb"]
            return

        required = {
            "ground_elevation": self.ground_elevation,
            "total_depth_rkb": self.total_depth_rkb,
            "depth_reference_rkb": self.depth_reference_rkb,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise ValueError(f"Provide header or explicit geometry values: {', '.join(missing)}")

    def add_table(self, name: str, **overrides) -> PressureTable:
        """
        Create, register, and return a new named PressureTable for this well.

        Any of ground_temperature/geothermal_gradient/rho_brine/shmin_gradient/
        shmin_data can be overridden per table, to run sensitivities on those
        assumptions while keeping the same depth range.
        """
        if name in self.tables:
            raise ValueError(f"Table {name!r} already exists")

        total_depth_msl = self.total_depth_rkb - self.depth_reference_rkb
        z_final = max(total_depth_msl, self.co2_datum) + 500
        depth = np.arange(0.0, z_final, self.depth_step)

        table = PressureTable(
            name=name,
            depth=depth,
            ground_elevation=self.ground_elevation,
            ground_temperature=overrides.pop("ground_temperature", self.ground_temperature),
            geothermal_gradient=overrides.pop("geothermal_gradient", self.geothermal_gradient),
            rho_brine=overrides.pop("rho_brine", self.rho_brine),
            shmin_gradient=overrides.pop("shmin_gradient", self.shmin_gradient),
            shmin_data=overrides.pop("shmin_data", self.shmin_data),
        )
        if overrides:
            raise TypeError(f"Unknown PressureTable overrides: {sorted(overrides)}")

        self.tables[name] = table
        return table

    def add_scenario(self, name: str, table_name: str = DEFAULT_TABLE_NAME, **kwargs) -> PressureScenario:
        """Create, register, and return a new PressureScenario anchored to the named PressureTable."""
        if name in self.scenarios:
            raise ValueError(f"Scenario {name!r} already exists")
        if table_name not in self.tables:
            raise ValueError(f"Table {table_name!r} does not exist; call add_table first")

        kwargs.setdefault("fluid_type", self.fluid_type)
        kwargs.setdefault("pvt_path", self.pvt_path)

        scenario = PressureScenario(name=name, table=self.tables[table_name], **kwargs)
        self.scenarios[name] = scenario
        return scenario

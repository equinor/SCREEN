from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.interpolate import RectBivariateSpline

from ..utils.compute_intersection import compute_intersection
from .co2_pressure import _get_rho_in_pressure_column, _integrate_pressure


@dataclass
class FluidP_scenario:
    header: dict

    ref_P: pd.DataFrame  # Init table with hydrostatic pressure, temperature and Shmin profile
    rho_CO2: RectBivariateSpline
    rho_H2O: RectBivariateSpline

    p_name: str = None

    p_delta: float = np.nan
    p_resrv: float = np.nan
    z_resrv: float = np.nan

    p_CO2_datum: float = np.nan
    z_CO2_datum: float = np.nan

    p_MSAD: float = np.nan  # Pressure at Minimum Safety Abandonement depth
    z_MSAD: float = np.nan  # Depth at Minimum Safety Abandonement depth

    P_table: pd.DataFrame = None

    def __post_init__(self):
        """
        Initialization. Depending on input defines which method to run.
        """
        if not np.isnan(self.z_MSAD):
            # class will compute max pressure for given points. Integration of CO2 downwards
            self.integrate_downwards()

        elif (not np.isnan(self.p_delta)) and (not np.isnan(self.z_resrv)):
            # reservoir pressure given as delta value- Integration of CO2 is upwards
            raise NotImplementedError("method not implemented yet")

        elif (not np.isnan(self.p_resrv)) and (not np.isnan(self.z_resrv)) and (not np.isnan(self.z_CO2_datum)):
            # reservoir pressure given as absolute value- Integration of CO2 is upwards
            self.integrate_upwards()

    def __repr__(self):
        p_resrv_abs = f"reservoir pressure:\t{self.p_resrv:.2f} @ {self.z_resrv} mTVDMSL"
        p_resrv_d = f"reservoir delta P:\t{self.p_delta} @ {self.z_resrv} mTVDMSL"
        p_MSAD = f"max pressure:\t\t{self.p_MSAD:.2f} @ {self.z_MSAD:.2f} mTVDMSL"
        z_datum = f"base of CO2:\t\t{self.z_CO2_datum} mTVDMSL"

        return f"Pressure scenario:\t{self.p_name}\n{p_resrv_abs}\n{p_resrv_d}\n{p_MSAD}\n{z_datum}"

    def integrate_upwards(self):
        """
        Method to compute pressure tables starting from reservoir pressure.
        """
        print(
            f"Pressure scenario {self.p_name}: Compute pressures assuming reservoir pressure is {self.p_resrv:.2f} bar at {self.z_resrv:.2f} mTVDMSL"
        )

        # Water
        p0 = self.p_resrv
        water_p_colname = "h2o"

        self.P_table = _integrate_pressure(
            well_header=self.header,
            pt_df_in=self.ref_P,
            get_rho=self.rho_H2O,
            reference_depth=self.z_resrv,
            reference_pressure=p0,
            direction="up",
            colname_p=water_p_colname,
        )

        self.P_table = _integrate_pressure(
            well_header=self.header,
            pt_df_in=self.P_table,
            get_rho=self.rho_H2O,
            reference_depth=self.z_resrv,
            reference_pressure=p0,
            direction="down",
            colname_p=water_p_colname,
        )

        # CO2
        p0 = np.interp(self.z_CO2_datum, self.P_table["depth_msl"], self.P_table[water_p_colname])
        self.p_CO2_datum = p0
        co2_p_colname = "co2"

        self.P_table = _integrate_pressure(
            well_header=self.header,
            pt_df_in=self.P_table,
            get_rho=self.rho_CO2,
            reference_depth=self.z_CO2_datum,
            reference_pressure=p0,
            direction="up",
            colname_p=co2_p_colname,
        )

        # We need the density for water given the CO2-pressures, too
        self.P_table = _get_rho_in_pressure_column(self.P_table, co2_p_colname, "h2o_rho_in_co2_column", self.rho_H2O)

        # Compute MSAD
        depth = self.P_table["depth_msl"].values
        shmin = self.P_table["Shmin"].values
        co2_p = self.P_table["co2"].values
        self.z_MSAD, self.p_MSAD = compute_intersection(x=depth, y1=shmin, y2=co2_p)

        # Compute delta P
        hs_p = np.interp(float(self.z_resrv), self.ref_P["depth_msl"], self.ref_P["hs_p"])

        self.p_delta = self.p_resrv - hs_p

    def integrate_downwards(self):
        """
        Method to compute maximum pressure tables starting from Shmin at given depth.
        """

        print(f"Pressure scenario {self.p_name}: Compute maximum pressurization needed to reach Shmin at {self.z_MSAD} mTVDMSL")

        # CO2
        co2_p_colname = "co2"
        self.p_MSAD = np.interp(float(self.z_MSAD), self.ref_P["depth_msl"], self.ref_P["Shmin"])

        self.P_table = _integrate_pressure(
            well_header=self.header,
            pt_df_in=self.ref_P,
            get_rho=self.rho_CO2,
            reference_depth=float(self.z_MSAD),
            reference_pressure=self.p_MSAD,
            direction="down",
            colname_p=co2_p_colname,
        )

        # Clean up pressure values below Gas_Water_contact
        self.P_table.loc[self.P_table["depth_msl"] > self.z_CO2_datum, co2_p_colname] = np.nan

        # Water
        p0 = np.interp(float(self.z_CO2_datum), self.P_table["depth_msl"], self.P_table[co2_p_colname])
        self.p_CO2_datum = p0
        water_p_colname = "h2o"

        self.P_table = _integrate_pressure(
            well_header=self.header,
            pt_df_in=self.P_table,
            get_rho=self.rho_H2O,
            reference_depth=self.z_CO2_datum,
            reference_pressure=p0,
            direction="up",
            colname_p=water_p_colname,
        )

        self.P_table = _integrate_pressure(
            well_header=self.header,
            pt_df_in=self.P_table,
            get_rho=self.rho_H2O,
            reference_depth=self.z_CO2_datum,
            reference_pressure=p0,
            direction="down",
            colname_p=water_p_colname,
        )

        # We need the density for water given the CO2-pressures, too
        self.P_table = _get_rho_in_pressure_column(self.P_table, co2_p_colname, "h2o_rho_in_co2_column", self.rho_H2O)

        # Compute reservoir pressure at CO2_datum
        hs_p = self.P_table["h2o"].values

        self.z_resrv = self.z_CO2_datum
        self.p_resrv = self.p_CO2_datum

        # Compute delta P
        hs_p = np.interp(float(self.z_resrv), self.ref_P["depth_msl"], self.ref_P["hs_p"])
        self.p_delta = self.p_resrv - hs_p

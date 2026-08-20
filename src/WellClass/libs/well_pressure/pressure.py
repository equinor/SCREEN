import json
from dataclasses import dataclass
from typing import Union

import numpy as np
import pandas as pd
from scipy.interpolate import RectBivariateSpline

from ..pvt.pvt import get_hydrostatic_P, get_pvt
from ..well_class.well_class import Well
from .barrier_pressure import compute_barrier_leakage
from .co2_pressure import _get_shmin
from .pressure_scenario import FluidP_scenario


@dataclass  # @dataclass(kw_only=True)
class Pressure:
    """This is used to compute leakeage rate of legacy well

    Args:
        header (dict): well header
        reservoir_P (dict): reservoir pressure
        co2_datum (float): co2 datum depth
        pvt_path (str): directory where PVT files are located.
    """

    header: dict = None
    reservoir_P: dict = None
    co2_datum: dict = None
    pvt_path: str = None
    barriers: dict = None
    max_pressure_pos: Union[dict, list, float, int] = None
    pressure_scenarios: dict = None

    def __post_init__(self):
        self._check_init_pressure()
        self._check_scenarios()
        self._compute_CO2_pressures()

    # TODO(hzh): non-pure function!!!
    def _check_init_pressure(self):
        """
        Calculates hydrostatic pressure at
        reservoir_P is the entry looking something like this:

        reservoir_pressure
        depth_msl	RP1	RP2
        2238		        20

        then P_init['depth_msl'] is the reference depth 2238

        Also delta-pressures RP1 and RP2 are read and used later for leakage calculations. (self.reservoir_P[])

        Note: The interpretation of the numbers set for RP1 and RP2 is a bit unclear. RP means reservoir pressure - but for the current
              implementation it is interpreted as delta pressure: delta wrt hydrostatic pressure.
              Initial implementation had the possibility to have absolute pressure AND a delta-pressure. But the delta-pressure had to be
              given as a string "+ 20" or "- 15". Bit the + and - tended to create problems.
              So alternatively one could distingwuish between RP and DP  if it is important to give in absolute pressure as well.
              But the most interesting input IS actually the change in pressure compared with hydrostatic pressure.

        """
        P_init = self.reservoir_P

        # Get hydrostatic pressure
        ref_z = P_init["depth_msl"]  # A reference depth given in the input, e.g. top reservoir
        hydrostaticP = get_hydrostatic_P(
            self.header, pvt_path=self.pvt_path
        )  # Calculate depth, temp(depth) hydrostatic_pressure(depth), H2ORHO(depth for hydrostatic pressure)

        ref_p = np.interp(ref_z, hydrostaticP["depth_msl"], hydrostaticP["hs_p"])  # Hydrostatic pressure at that depth
        print(f"Hydrostatic pressure at reference depth {ref_z:.0f} is {ref_p:.2f}")

        self.reservoir_P["hydrostatic_pressure"] = ref_p

        self.pressure_CO2 = hydrostaticP  # store table as pressure_CO2

    def _check_scenarios(self):
        MAX_PRESSURE_NAME = "max_p"

        self.pressure_scenarios = {}

        ref_p = self.reservoir_P["hydrostatic_pressure"]
        scenario_counter = 1

        # Iterate over reservoir pressure scenarios (values under reservoir_P table)
        for sc_name, sc_pressure in self.reservoir_P.items():
            if sc_name == "RP1":
                if sc_pressure is None or np.isnan(sc_pressure):
                    print(f"RP1 set as hydrostatic P = {ref_p:.2f} bar")
                    magnitude = ref_p

                else:
                    print(f"RP1 is set as delta pressure, which yields P = {ref_p:.2f} {sc_pressure:+.2f} = {ref_p + sc_pressure:.2f} bar")
                    magnitude = ref_p + sc_pressure

                self.pressure_scenarios[scenario_counter] = {"name": sc_name, "p_resrv": magnitude, "type": "reservoir"}
                scenario_counter += 1

            elif sc_name.startswith("RP"):
                magnitude = sc_pressure

                try:
                    if isinstance(magnitude, str):
                        magnitude = magnitude.replace(" ", "")

                    magnitude = float(magnitude)

                except Exception:
                    pass

                if isinstance(magnitude, float) or isinstance(magnitude, int):
                    # p = ref_p + RP                          #self.reservoir_P['RP1'] + RP
                    print(f"{sc_name} is set as delta pressure, which yields P = {ref_p:.2f} {magnitude:+.2f} = {ref_p + magnitude:.2f} bar")
                    magnitude = ref_p + magnitude

                    self.pressure_scenarios[scenario_counter] = {"name": sc_name, "p_resrv": magnitude, "type": "reservoir"}
                    scenario_counter += 1

                else:
                    print(sc_name, "ignored")
                    continue

        # Iterate over maximum pressure scenarios (values entered under max_pressure_pos)
        if isinstance(self.max_pressure_pos, dict):
            print("max_pressure_pos is a dictionary of plug positions")
            for idx, key in self.max_pressure_pos["barrier_name"].items():
                plug_depth = self.max_pressure_pos["bottom_msl"][idx]
                sc_name = f"{MAX_PRESSURE_NAME}_{key}"

                self.pressure_scenarios[scenario_counter] = {"name": sc_name, "z_MSAD": plug_depth, "type": "max_p"}
                scenario_counter += 1

        elif isinstance(self.max_pressure_pos, (list, float, int)):
            print("max_pressure_pos is a value")
            if isinstance(self.max_pressure_pos, (float, int)):  # Make it a list with one element
                self.max_pressure_pos = [self.max_pressure_pos]

            for depth in self.max_pressure_pos:
                sc_name = f"{MAX_PRESSURE_NAME}_at_{int(depth)}"
                self.pressure_scenarios[scenario_counter] = {"name": sc_name, "z_MSAD": depth, "type": "max_p"}
                scenario_counter += 1

    def _compute_CO2_pressures(self):
        """
        The pressure and density for H2O and CO2  along the columns are calculated using an approximate integration
        Hydrostatic pressure - caculatong downwards from msl
        Pressure and density assuming a water column - starting at top reservoir and the given overpressure RP
        Pressure and density assuming a CO2   column - starting at CO2-reference level (CO2-column could start below top reservoir) and the given overpressure RP
        Shmin

        Input:
        max_pressure_pos is a depth from where max pressure (wrt Shmin) is calculated. It can be a plug-position table, a list of numbers, or a scalar.
            If a plug-position table is given, pressure is calculated from the base of each plug.

        Columns are
            |--------------------init---------------------------------------------|---------------------RPx----------------------------------|
            depth_msl        temp          hs_p          RHOH20            Shmin   h2o            h20_rho         co2                            RPx_co2_rho     RPx_h2o_rho_in_co2_column
            depth below msl   temperature   hydrostatic  water density             hs_p+          densities at    Pressure given a CO2 column        Corresponding   water densitites if we are
            depth ref for                   pressure     at hydrostatic            overpressure   RPx_h20         and overpressure RP                CO2 densities   in a CO2-column.
            all other values                column       pressure                  RPx



        ---> The RP are all RP-input + hydrostatic_pressure. Hence if e.g. RP1 is hydrostatic pressure RP1-columns and hydrostatic_pressure-columns are identical.
        """

        self.pressure_CO2 = _get_shmin(self.header, self.pressure_CO2)

        # Retrieve pressure, temperature and density fields for CO2 and H2O
        pvt_T, pvt_P, pvt_RHO_CO2, pvt_RHO_H2O = get_pvt(self.pvt_path)

        # An interpolator. Used later to look-up densities given pressure p and temperature t
        get_rho_h2o = RectBivariateSpline(pvt_P, pvt_T, pvt_RHO_H2O)
        get_rho_co2 = RectBivariateSpline(pvt_P, pvt_T, pvt_RHO_CO2)

        # Define and assign a multiindex that groups columns generic for all scenarios: depth_msl, temp, hs_p, RHOH2O and Shmin
        index_init = pd.MultiIndex.from_product([["init"], self.pressure_CO2.columns])
        self.pressure_CO2.columns = index_init

        # iterate over pressure scenarios to compute tables:
        for press_sc in self.pressure_scenarios:
            sc_name = self.pressure_scenarios[press_sc]["name"]
            sc_type = self.pressure_scenarios[press_sc]["type"]

            if sc_type == "reservoir":
                p_resrv = self.pressure_scenarios[press_sc]["p_resrv"]
                sc_pressure = FluidP_scenario(
                    header=self.header,
                    ref_P=self.pressure_CO2["init"],
                    rho_H2O=get_rho_h2o,
                    rho_CO2=get_rho_co2,
                    p_name=sc_name,
                    p_resrv=p_resrv,
                    z_resrv=self.reservoir_P["depth_msl"],
                    z_CO2_datum=self.co2_datum,
                )

                self.pressure_scenarios[press_sc]["p_MSAD"] = sc_pressure.p_MSAD
                self.pressure_scenarios[press_sc]["z_MSAD"] = sc_pressure.z_MSAD
                self.pressure_scenarios[press_sc]["z_resrv"] = sc_pressure.z_resrv
                self.pressure_scenarios[press_sc]["p_delta"] = sc_pressure.p_delta

            elif sc_type == "max_p":
                msad = self.pressure_scenarios[press_sc]["z_MSAD"]

                sc_pressure = FluidP_scenario(
                    header=self.header,
                    ref_P=self.pressure_CO2["init"],
                    rho_H2O=get_rho_h2o,
                    rho_CO2=get_rho_co2,
                    p_name=sc_name,
                    z_MSAD=msad,
                    z_CO2_datum=self.co2_datum,
                )

                self.pressure_scenarios[press_sc]["p_MSAD"] = sc_pressure.p_MSAD
                self.pressure_scenarios[press_sc]["p_resrv"] = sc_pressure.p_resrv
                self.pressure_scenarios[press_sc]["z_resrv"] = sc_pressure.z_resrv
                self.pressure_scenarios[press_sc]["p_delta"] = sc_pressure.p_delta

            else:
                continue

            # Drop repeated columns
            sc_pressure.P_table = sc_pressure.P_table.drop(columns=self.pressure_CO2["init"].columns)

            # Setup multiindex
            index_table = pd.MultiIndex.from_product([[sc_name], sc_pressure.P_table.columns])
            sc_pressure.P_table.columns = index_table

            # Concatenate init table with scenario table
            self.pressure_CO2 = pd.concat([self.pressure_CO2, sc_pressure.P_table], axis=1)

    def compute_barrier_leakage(self, well: Well, barrier_name: str) -> pd.DataFrame:
        """Compute leakage rate from the given barrier

        Args:
            well (Well): well information
            barrier_name (str): barrier to check the leakage rate
        """

        # for convenience
        barrier_perm = well.barrier_perm

        # barrier geometries
        barrier_props = well.compute_barrier_props(barrier_name)

        # Estimate CO2 leakage in [tons/day] after a trancient period
        barrier_leakage = compute_barrier_leakage(barrier_perm, self.pressure_scenarios, self.pressure_CO2, barrier_props)

        return barrier_leakage

    @property
    def to_json(self):
        return json.dumps(self.__dict__, indent=4)

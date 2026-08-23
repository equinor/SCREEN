from pathlib import Path
from typing import Callable, Tuple, Union

import numpy as np
import pandas as pd
import scipy.constants as const
from scipy.integrate import solve_ivp
from scipy.interpolate import RectBivariateSpline

"""Some global parameters"""
G = const.g  # 9.81 m/s2 gravity acceleration


def default_pvt_path() -> Path:
    """Return the bundled CO2 PVT collection shipped with WellClass."""
    return Path(__file__).resolve().parents[2] / "data" / "pvt" / "co2"


def get_pvt(pvt_path: str | Path | None = None) -> tuple:
    """Reads the vectors for pressure and temperature and the matrix for rho
    Note that the values for temperature and rho must be aligned with values in rho
    Note also for rho: One temperature for each column
                       One pressure for each row
    It applies a salinity correction for a concentration of 3.5 gNaCl in 100 g H2O
    based on the work done by
    LALIBERTÉ, M. & COOPER, W. E. 2004. Model for Calculating the Density of
    Aqueous Electrolyte Solutions. Journal of Chemical & Engineering Data, 49,
    1141-1151.
    https://www.calsep.com/13-density-of-brine/
    """
    pvt_root = Path(pvt_path) if pvt_path is not None else default_pvt_path()
    fn_temp = pvt_root / "temperature.txt"
    fn_pres = pvt_root / "pressure.txt"
    fn_rho_co2 = pvt_root / "rho_co2.txt"
    fn_rho_h2o = pvt_root / "rho_h2o.txt"

    t = np.loadtxt(fn_temp)
    p = np.loadtxt(fn_pres)
    rho_co2 = np.loadtxt(fn_rho_co2, delimiter=",")
    rho_h2o = np.loadtxt(fn_rho_h2o, delimiter=",")

    # compute 2d matrices for pressure and temperature
    t_grid, p_grid = np.meshgrid(t, p)

    ## Laliberté and Cooper model for NaCl solutions
    # Laliberté and Cooper model: constants for NaCl
    c0 = -0.00433
    c1 = 0.06471
    c2 = 1.0166
    c3 = 0.014624
    c4 = 3315.6

    # NaCl concentration
    # TODO(gpb): Include salinity as input
    w = 3.5 / 100

    # Laliberté and Cooper model: Apparent density
    rho_app = (c0 * w + c1) * np.exp(0.000001 * (t_grid + c4) ** 2) / (w + c2 + c3 * t_grid)

    # Laliberté and Cooper model: Brine density
    rho_brine = 1 / (((1 - w) / rho_h2o) + (w / rho_app))

    return t, p, rho_co2, rho_brine


# Compute the temperature given the input gradient
def compute_T(z: Union[float, int], well_header: dict) -> float:
    T = well_header["sf_temp"] + max(0, z - well_header["sf_depth_msl"]) * (well_header["geo_tgrad"] / 1000)
    return T


# Ordinary Differential Equation (ODE) system for the pressure and density
def odesys(z: float, y: np.ndarray, well_header: dict, rho_getter: Callable) -> Tuple[float]:
    P = y[0]
    T = compute_T(z, well_header)
    rho = rho_getter(P, T)[0, 0]
    dPdz = rho * const.g / const.bar
    return (dPdz,)


def get_hydrostatic_P(well_header: dict, *, dz=1, pvt_path: str | Path | None = None) -> pd.DataFrame:
    """Simple integration to get the hydrostatic pressure at a given depth
    Does also calculates the depth column, temperatur vs depth and water density (RHOH2O) vs depth (hydrostatic)
    """
    t_vec, p_vec, rho_co2_vec, rho_h2o_vec = get_pvt(pvt_path)

    # Make the depth-vector from msl and downwards
    total_depth_rkb = well_header.get("total_depth_rkb", well_header.get("well_td_rkb"))
    depth_reference_rkb = well_header.get("depth_reference_rkb", well_header.get("well_rkb"))
    if total_depth_rkb is None or depth_reference_rkb is None:
        raise KeyError("Well header requires total/depth-reference RKB values")

    td_msl = total_depth_rkb - depth_reference_rkb
    z_final = int(td_msl) + 500
    z_vec = np.arange(0, z_final, dz)

    # Create dataframe for storing pressures and temperatures. hs_p_df -> HydroStatic_Pressure_DataFrame
    hs_p_df = pd.DataFrame(data=z_vec, columns=["depth_msl"])

    # Compute temperature. Constant in water column and as a function of input geothermal gradient
    hs_p_df["temp"] = hs_p_df["depth_msl"].map(lambda z: compute_T(z, well_header))

    ##Integrate hydrostatic pressure

    # Initial conditions: Pressure (atm), depth and temperature at msl
    z_0 = 0
    P_0 = const.atm / const.bar

    # Make interpolators for the imported tables
    get_rho_h2o = RectBivariateSpline(p_vec, t_vec, rho_h2o_vec)

    # Solve ODEs from z = 0 to the final depth (well depth)
    solution = solve_ivp(odesys, [z_0, z_final], [P_0], args=(well_header, get_rho_h2o), t_eval=hs_p_df["depth_msl"].values)

    # Store the solution in Dataframe
    hs_p_df["hs_p"] = solution.y[0]

    return hs_p_df

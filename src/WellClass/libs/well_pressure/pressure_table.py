from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Union
import numpy as np
from scipy import constants as const

def shmin_data_interpolator(shmin_data:List[List[float]], depth_array:np.ndarray, ground_elevation:float, ground_pressure_bar:float, surface_pressure_bar:float) -> np.ndarray:

    shmin_data = np.array(shmin_data)
    depth_values, shmin_values = shmin_data.T

    # Remove duplicates while keeping the first occurrence
    unique_indices = np.unique(depth_values, return_index=True)[1]
    depth_values = depth_values[np.sort(unique_indices)]
    shmin_values = shmin_values[np.sort(unique_indices)]


    if min(depth_values) > ground_elevation:
        warnings.warn(
            f"No Shmin data between seafloor depth ({ground_elevation}) and minimum provided depth ({min(depth_values)}). "
            "Extrapolating using hydrostatic pressure at seafloor."
        )

    else:
        filtered_depth_values = depth_values[depth_values >= ground_elevation]
        filtered_shmin_values = shmin_values[depth_values >= ground_elevation]

        depth_values = filtered_depth_values
        shmin_values = filtered_shmin_values

    # Insert the seafloor depth and pressure at mudline into the arrays
    depth_values = np.insert(depth_values, 0, ground_elevation)
    shmin_values = np.insert(shmin_values, 0, ground_pressure_bar)


    # Insert values af MSL
    depth_values = np.insert(depth_values, 0, 0)
    shmin_values = np.insert(shmin_values, 0, surface_pressure_bar)


    shmin_interpolator = interp1d(depth_values, shmin_values, bounds_error=False, fill_value="extrapolate")

    shmin_curve = shmin_interpolator(depth_array)
    return shmin_curve



@dataclass
class PressureTable:
    name: str
    depth: np.ndarray  # depth array (m)

    # Input parameters
    ground_elevation: float  # ground elevation (m)
    ground_temperature: float  # ground temperature (°C)
    geothermal_gradient: float  # geothermal gradient (°C/km)
    rho_brine : float = 1030  # brine density (kg/m³)

    # Minimum horizontal stress parameters
    shmin_gradient: float = 0.1695
    shmin_data: List[List[float]] = field(default=None)  # depth values for shmin data

    # Computed arrays
    temperature: np.ndarray = field(init=False) # temperature array (°C)
    hydrostatic_pressure: np.ndarray = field(init=False)   # hydrostatic pressure (MPa or bar)
    min_horizontal_stress: np.ndarray  = field(init=False) # minimum horizontal stress (MPa or bar)
    # fluid_pressure: np.ndarray  # fluid pressure (MPa or bar)
    # brine_pressure: np.ndarray  # brine pressure (MPa or bar)
    # min_horizontal_stress: np.ndarray  # minimum horizontal stress (MPa or bar)

    def __post_init__(self):
        # Compute temperature array based on depth and geothermal gradient
        self.temperature = self.compute_temperature()
        self.hydrostatic_pressure = self.compute_hydrostatic_pressure()
        self.min_horizontal_stress = self.compute_shmin()
    #     lengths = {
    #         'depth': len(self.depth),
    #         'temperature': len(self.temperature),
    #         'hydrostatic_pressure': len(self.hydrostatic_pressure),
    #         'fluid_pressure': len(self.fluid_pressure),
    #         'brine_pressure': len(self.brine_pressure),
    #         'min_horizontal_stress': len(self.min_horizontal_stress),
    #     }
    #     unique_lengths = set(lengths.values())
    #     if len(unique_lengths) != 1:
    #         raise ValueError(f"All arrays must have the same length, but got lengths: {lengths}")
        

    def compute_temperature(self) -> np.ndarray:
        """Compute temperature at a given depth using the geothermal gradient."""

        temp_array = self.ground_temperature + (self.geothermal_gradient * (self.depth - self.ground_elevation) / 1000)

        temp_array[self.depth < self.ground_elevation] = self.ground_temperature

        return temp_array
    
    def compute_hydrostatic_pressure(self) -> np.ndarray:
        pressure_pa = const.atm + self.depth * self.rho_brine * const.g
        pressure_bar = pressure_pa / 1e5
        return pressure_bar
    
    def compute_shmin(self) -> np.ndarray:
        """Compute minimum horizontal stress at a given depth."""
        # Placeholder: linear increase with depth, can be replaced with a more complex model
        
        ground_pressure = np.interp(self.ground_elevation, self.depth, self.hydrostatic_pressure)


        if self.shmin_data:


            return shmin_data_interpolator(shmin_data=self.shmin_data, depth_array=self.depth, ground_elevation=self.ground_elevation, ground_pressure_bar=ground_pressure, surface_pressure_bar=const.atm/1e5)

        else:
            raise ValueError("Either shmin_gradient or shmin_data must be provided.")




    def get_values_at_depth(self, depth_value: float) -> dict:
        """Interpolate all curves at a given depth."""

        def interp(arr):
            f = interp1d(self.depth, arr, bounds_error=False, fill_value="extrapolate")
            return float(f(depth_value))  # convert numpy float to Python float
    
        return {
            "temperature": interp(self.temperature),
            "hydrostatic_pressure": interp(self.hydrostatic_pressure),
            # "fluid_pressure": interp(self.fluid_pressure),
            # "brine_pressure": interp(self.brine_pressure),
            "min_horizontal_stress": interp(self.min_horizontal_stress),
        }
    

# @dataclass
# class Pressure:
#     ground_elevation: float
#     total_depth_msl: float

#     def __post_init__(self):
#         self.pressure_tables: List[PressureTable] = []

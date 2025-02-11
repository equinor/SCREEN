The SCREEN scripts facilitate preliminary analysis by generating two main outputs from the input data:

- A wellbore schematic that integrates geological well tops from subsurface data.
- A pressure depth plot that models the pressure profile along the wellbore.

Users provide input data in CSV or YAML format, which includes the following required parameters:

- `well_header`: General well information such as `well_name`, `well_rkb`, `sf_depth_msl`, `well_td_rkb`, `sf_temp`, and `geo_tgrad`.
- `drilling` table: Interval data for hole sections with top and bottom depths and diameters.
- `casing_cement` table: Casing and cement records by top and bottom depth, inner diameter, and cement top (TOC) and bottom (BOC) depths. A `shoe` flag and a `permeability` value are included.
- `barriers` table`: Depths of cement or mechanical plugs with a `permeability` value for modeling.
- `geology` table`: Geological unit tops, names, and a reservoir indicator. Overburden flow units must be tagged as reservoirs.
- `reservoir_pressure`: (to be deprecated) Reference for pressure deviations at the reservoir level.
- `co2_datum`: Depth of the expected base of the gas column, indicating aquifer pressure conditions.

Examples in the `test_data` folder can be used as templates for structuring the data. The `pflotran_gap` notebook serves as a reference guide to execute the workflow. The initial step involves using the `Well` data class to construct the well object:

```python
my_well = Well(header       = well_csv['well_header'], 
               drilling     = well_csv['drilling'],
               casings      = well_csv['casing_cement'],
               geology      = well_csv['geology'],
               barriers     = well_csv['barriers'], 
               barrier_perm = well_csv['barrier_permeability'],
               co2_datum    = well_csv['co2_datum'])

```

During this process, all inputs are converted to meters, and depth values are harmonized to be expressed in meters below mean sea level (mMSL). After this conversion, it is possible to generate a visualization of the wellbore schematic.

The Well object is then utilized to instantiate the Pressure class and create pressure profiles:

```python
my_pressure = Pressure(header      = well_csv['well_header'],
                       reservoir_P = well_csv['reservoir_pressure'],
                       co2_datum   = well_csv['co2_datum'],
                       pvt_path    = pvt_path)
```
These profiles are approximations derived from a numerical method that computes pressure. The script begins with known temperature and pressure at a reference depth to calculate initial fluid density. It then applies the equation  `ΔP=ρ⋅g⋅dz`, iteratively updating pressure and density over small depth increments. At each step, the new pressure is determined using the updated density and the known temperature gradient, continuing this process throughout the well's depth profile. The integration of differential equations for pressure and density calculations was initially performed using a conventional for loop, but has since been optimized by adopting the solve_ivp method from scipy.integrate, enhancing both efficiency and accuracy.

## Limitations

- The wellbore schematic does not have functionalities to represent internal tubing, casing perforations or multiple discrete cemented sections.
- Identified overburden flow units should be labeled as reservoirs in the input data.
- Permeability values in the `casing_cement` and `barriers` tables are estimates provided by the user. These values are subject to significant uncertainty due to factors such as cement quality, curing defects, or fractures, and can vary across orders of magnitude. Users are responsible for providing realistic permeability estimates, drawing on professional judgment and available literature in the absence of concrete data.
- The estimation of fluid pressure using the `Pressure` class is not a full-fledged simulation but a numerical approach that approximates shut-in pressures or a system in equilibrium. It should not be confused with dynamic simulation models that account for transient conditions and fluid flow in the reservoir and wellbore.


![Effective permeability range for well cement, highlighting variability and uncertainty.](link-to-attached-figure-permeability-variance)
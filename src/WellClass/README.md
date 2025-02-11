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
These profiles are approximations derived from a numerical method that computes pressure. The script begins with known temperature and pressure at a reference depth to calculate initial fluid density. It then applies the equation  `ΔP=ρ⋅g⋅dz`, iteratively updating pressure and density over small depth increments. At each step, the new pressure is determined using the updated density and the known temperature gradient, continuing this process throughout the well's depth profile. The integration of differential equations for pressure and density calculations was initially performed using a conventional for loop, but has since been optimized by adopting the `solve_ivp` method from `scipy.integrate`, enhancing both efficiency and accuracy.

Once the `Well` and `Pressure` instances have been created, they can be visualized using the `plot_sketch` and `plot_pressure` functions. The `plot_sketch` function provides a schematic of the wellbore, while the `plot_pressure` function produces a pressure versus depth plot.

![Combined visualization of wellbore schematic and pressure depth plot.](imgs/screen_wellsch_example.png)
*Figure 1: Combined visualization of wellbore schematic and pressure depth plot.*

Additionally, the `plot_pt` function allows for the visualization of profiles in a Pressure-Temperature plot, which includes phase boundaries and background coloring to indicate fluid density changes.

![Pressure profile from `Pressure` instance displayed in a Pressure-Temperature Plot with phase boundaries and fluid density as background color.](imgs/PT_diagram_example.png)
*Figure 2: Pressure profile from `Pressure` instance displayed in a Pressure-Temperature Plot with phase boundaries and fluid density as background color.*


## Limitations

- The wellbore schematic does not have functionalities to represent internal tubing, casing perforations or multiple discrete cemented sections.
- Identified overburden flow units should be labeled as reservoirs in the input data.
- Permeability values in the `casing_cement` and `barriers` tables are estimates provided by the user. These values are subject to significant uncertainty due to factors such as cement quality, curing defects, or fractures, and can vary across orders of magnitude. Users are responsible for providing realistic permeability estimates, drawing on professional judgment and available literature in the absence of concrete data.
- The estimation of fluid pressure using the `Pressure` class is not a full-fledged simulation but a numerical approach that approximates shut-in pressures or a system in equilibrium. It should not be confused with dynamic simulation models that account for transient conditions and fluid flow in the reservoir and wellbore.



![Range of effective permeability magnitude in cement materials from different sources. Laboratory-Measured: A, B, C, D are permeability measured directly on cement samples. Field-Estimated: E, F, G, H are permeability values inferred from field observations and measurements. Used for Modeling: I is permeability ranges or values used as input parameters in numerical simulations.](imgs/cement_perm.png)
*Figure 3: Range of effective permeability in cement materials. Laboratory-Measured: A[1], B[2], C[3], D[4]. Field-Estimated: E[5], F[6], G[6], H[6]. Used for Modeling: I[7].*

## References

1. Beltrán-Jiménez, K., Gardner, D., Kragset, S., Gebremariam, K. F., Reales, O. A. M., Minde, M. W., de Souza, M. I. L., Aasen, J. A., Skadsem, H. J., & Delabroy, L. (2022). Cement properties characterization from a section retrieved from an oil production well after 33 years of downhole exposure. Journal of Petroleum Science and Engineering, 208, 109334. https://doi.org/10.1016/j.petrol.2021.109334

2. Gasda, S. E., Celia, M. A., Wang, J. Z., & Duguid, A. (2013). Wellbore Permeability Estimates from Vertical Interference Testing of Existing Wells. Energy Procedia, 37, 5673-5680. https://doi.org/10.1016/j.egypro.2013.06.489

3. Crow, W., Carey, J. W., Gasda, S., Brian Williams, D., & Celia, M. (2010). Wellbore integrity analysis of a natural CO2 producer. International Journal of Greenhouse Gas Control, 4(2), 186-197. https://doi.org/10.1016/j.ijggc.2009.10.010

4. Carey, J. W., Wigand, M., Chipera, S. J., WoldeGabriel, G., Pawar, R., Lichtner, P. C., Wehner, S. C., Raines, M. A., & Guthrie, G. D. (2007). Analysis and performance of oil well cement with 30 years of CO2 exposure from the SACROC Unit, West Texas, USA. International Journal of Greenhouse Gas Control, 1(1), 75-85. https://doi.org/10.1016/S1750-5836(06)00004-1

5. Kang, M., Baik, E., Miller, A. R., Bandilla, K. W., & Celia, M. A. (2015). Effective Permeabilities of Abandoned Oil and Gas Wells: Analysis of Data from Pennsylvania. Environmental Science & Technology, 49(7), 4757-4764. https://doi.org/10.1021/acs.est.5b00132

6. Carey, J. W. (2018). Probability distributions for effective permeability of potentially leaking wells at CO2 sequestration sites. Los Alamos National Lab.(LANL), Los Alamos, NM (United States). https://doi.org/10.18141/1433164

7. Godoy, R., Fontan, M., Capra, B., Kvalsund, R., & Poupard, O. (2015). Well Integrity Support by Extended Cement Evaluation - Numerical Modeling of Primary Cement Jobs. Abu Dhabi International Petroleum Exhibition and Conference. https://doi.org/10.2118/177612-MS


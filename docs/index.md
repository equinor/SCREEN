# SCREEN

# Introduction

The SCript-based Risk Estimation of well leakage in Early phase evaluatioN (SCREEN) project targets legacy well assessment for Carbon Capture and Storage (CCS) projects. Given that abandoned or inactive wells can serve as pathways for CO2 leakage, rigorous risk assessments and integrity evaluations are crucial [1; 2].

SCREEN provides a script-based workflow to streamline analysis in legacy well evaluations, improving data processing and analysis for well integrity engineers and subsurface teams.

Two primary modules constitute the SCREEN project: the pre-processing and preliminary assessment module, and the detailed simulation workflow using the PFLOTRAN tool (Figure 1.1). Preliminary assessments apply to all legacy wells, contingent on data availability, and are a focus of ongoing development for the WINC deliverable. The simulation module serves to quantify potential leakage rates where necessary after initial assessment outcomes.

While the simulation workflow includes modelling of key well integrity risks, it is not comprehensive for scenarios like material degradation or overburden fracturing. Specialists must assess these risks using different tools. For overburden leakage risks, a REVEAL-based workflow, stemming from SCREEN, is recommended (Figure 1.1).

![Figure 1.1 - Schematic workflow for assessment of legacy wells, highlighting where the SCREEN deliverables (marked in red) fit and when should be used.](imgs/screen_workflow.png)

## Data Preparation

Data preparation is a prerequisite for employing SCREEN workflows. This task involves gathering wellbore and subsurface data necessary for subsequent analysis, focusing on completeness for reliable evaluation outcomes.

The required data types for legacy well analyses are:

- **Well Headers**: Data such as well location, type, time of abandonment, and water depth.
- **Well Construction Details**: Information on drilling, completion, and abandonment processes, including borehole sizes, casings, and cement records.
- **Subsurface Information**: Geological data, including lithology and formation tests, required to identify potential barriers and flow paths.
- **Assumed Parameters**: Estimates for parameters such as reservoir fluid composition, geothermal gradient, overburden strength, and CO2 column size or CO2-water contact depth, in the absence of direct measurements.

Data can originate from databases such as SMDA and Wellcom, but it is the users' responsibility to input this data into SCREEN workflows manually or via other applications. Notably, the implementation within the WINC platform automates data retrieval from databases prior to running the SCREEN modules (Figure 1.2).

For clarification, SCREEN workflows do not interact with databases directly but rely on user-provided data, manually entered or sourced from other systems.

![Figure 1.2 - Schematic flow chart of the data types needed for a legacy well evaluation](imgs/SCREEN_DataFlow.png)

### References

1. ISO. (2017). ISO 27914:2017 Carbon dioxide capture, transportation and geological storage — Geological storage. Retrieved from [https://www.iso.org/standard/64148.html](https://www.iso.org/standard/64148.html)
2. DNV. (2019). DNV-RP-J203 Geological storage of carbon dioxide. Retrieved from [https://www.dnv.com/oilgas/download/dnv-rp-j203-geological-storage-of-carbon-dioxide.html](https://www.dnv.com/oilgas/download/dnv-rp-j203-geological-storage-of-carbon-dioxide.html)




<!-- # SCREEN

**SCREEN stands for "<ins>S</ins>imulation-based <ins>C</ins>omparative <ins>R</ins>isk <ins>E</ins>stimation of well leakage in <ins>E</ins>arly phase evaluatio<ins>N</ins>".**



## Introduction

The <a href="https://colab.equinor.com/technologies/4FAAF5BD-19C3-46A3-ACB6-5D38DD2C7A89/summary" target="_blank">SCREEN project</a> shall provide a workflow and a toolbox to assess CO2 leakage through abandoned wells. 

In addition to adjacent activities run internally and externally, the project aims to deliver a series of scrip-based tools to assist risk assesment of legacy wells and modelling leakage.
 
The toolbox can be grouped in two main modules: A **pre-processing and preliminary assesment**, and a **detailed simulation workflow** as shown in the figure below.

![fig1](imgs/screen_workflow.png)


### Pre-processing and preliminary assesment

#### Data Preparation

The first step in using the SCREEN toolbox is to gather all the necessary data. Sources of data include both subsurface data nearby well and specifics about the well construction. Some of this data can ba gathered from internal databases, but some other has to be retrieved manually. Whichever the method, the current solution requires the data to be collected on an input sheet (CSV or YAML file) with tables containing different datasets.

To collect the data these are some steps that can be followed:

•	*Identify the required data*: Review the list of required tables and columns in the input data file to determine what information you need to gather. This includes well header information, drilling intervals, casing and cementing intervals, barriers, geological units, and assumptions (see table below).

•	*Collect the data*: Involve both subsurface and well integrity experts involved on the project to provide curated datasets to be used in the evaluation. By doing this, we ensure data has been previously verified. Subsurface data can vary from simple well tops, temperature profiles to more specifics about the quality of the reservoirs involved, potential flow units in the overburden, and the current state of reservoir pressure in case it deviates from hydrostatic. A previous qualitative leakage risk assessment of the wells shall provide the necessary input relevant for the well.

•	*Organize the data*: Organize the data into tables according to the structure of the input data file. Use a spreadsheet program or a text editor to create a CSV file with multiple tables, each separated by a blank line. Ensure that all required tables and columns are included in the input data file and that the data is entered correctly.

•	*Include assumptions*: The assumptions depend on the stage of knowledge of the area. If there is a reservoir model in place, such model should be used to fill in the information for these tables. Otherwise, these should be discussed with the subsurface personnel involved in the project.

The input sheet could be defined as aither a YAML or a CSV file. It shall include the following tables:


| Category    |  Item                     |  Property                                           |  Source                     | Sketch                     | Simulation         |
|-------------|---------------------------|-----------------------------------------------------|-----------------------------|----------------------------|--------------------|
| Well        |  Well header              |  well name                                          |  well reports   / database  | :heavy_check_mark:         | :heavy_check_mark: |
| Well        |  Well header              |  well RKB                                           |  well reports   / database  | :heavy_check_mark:         | :heavy_check_mark: |
| Well        |  Well header              |  well td                                            |  well reports   / database  | :heavy_check_mark:         | :heavy_check_mark: |
| Well        |  Well header              |  water depth /   mudline depth                      |  well reports   / database  | :heavy_check_mark:         | :heavy_check_mark: |
| Well        |  Bitsize records          |  Top and   bottom depth (MD RKB), diameter          |  well reports               | :heavy_check_mark:         | :heavy_check_mark: |
| Well        |  Bitsize records          |  Permeability*                                      |  assumed                    | :x:                        | :heavy_check_mark: |
| Well        |  Casings                  |  Top and   bottom depth (MD RKB), diameter          |  well reports               | :heavy_check_mark:         | :heavy_check_mark: |
| Well        |  Casings                  |  Permeability*                                      |  assumed                    | :x:  				       | :heavy_check_mark: |
| Well        |  Cement bond              |  Min, max and   most likely top and bottom depth    |  well   assesment           | :heavy_check_mark:         | :heavy_check_mark: |
| Well        |  Cement bond              |  Permeability*                                      |  assumed /   well assesment | :x:                    	   | :heavy_check_mark: |
| Well        |  Barriers/cement plugs    |  Min, max and   most likely top and bottom depth    |  well   assesment           | :heavy_check_mark:         | :heavy_check_mark: |
| Well        |  Barriers/cement plugs    |  Permeability*                                      |  assumed /   well assesment | :x:     				   | :heavy_check_mark: |
| Subsurface  |  Geological tops          |  Top depth (MD   RKB)                               |  well reports   / database  | :heavy_check_mark:         | :heavy_check_mark: |
| Subsurface  |  Geological tops          |  Transport   properties (porosity, permeability)**  |  assumed    / asset         | :heavy_check_mark:         | :heavy_check_mark: |
| Subsurface  |  Geothermal info          |  Seafloor   temperature                             |  assumed    / asset         | :heavy_check_mark:         | :heavy_check_mark: |
| Subsurface  |  Geothermal info          |  Temperature   survey (if available)                |  assumed    / asset         | :heavy_check_mark:         | :heavy_check_mark: |
| Subsurface  |  Geothermal info          |  Geothermal   gradient                              |  assumed    / asset         | :heavy_check_mark:         | :heavy_check_mark: |
| Subsurface  |  Initialization           |  Reservoir   pressure (scenarios)                   |  asset                      | :heavy_check_mark:         | :heavy_check_mark: |
| Subsurface  |  Initialization           |  Base of CO2   (CO2-water contact depth)            |  asset                      | :heavy_check_mark:         | :heavy_check_mark: |

*permeability can be declared as good, average, poor
**flow units declaration





### Data Visualization and Proxy-based Leakage Estimation

Once all the information is tabulated, it can be processed with a python script. The processing will store the data in memory and use it to produce a hybrid geological well-sketch and a pressure-depth plot displaying the fluid pressures of each phase and the minimum horizontal stress.

The well sketch combines both subsurface data and well engineering information. It serves as a starting point to identify the main leakage pathways and illustrate the main risks associated with the well.

The pressure plot, besides visualizing the provided pressure scenarios, has the necessary input to run a preliminary leakage estimation based on a Darcy-based proxy. This proxy gives an estimate of leakage rates through the main barrier (deepest cement plug). The magnitude will be a function of both the transport properties assigned to the barrier and the resulting phase pressures of each scenario.

![well sketch](imgs/well-sketch.png)


## Detailed simulation workflow

For wells with larger uncertainties and more complex leakage pathways, a simulation-based approach can assist in generating a more accurate estimate of leakage.

By fulfilling the first two modules, the data is ready to be processed through a second script that generates and initializes a simple reservoir model with a finite-volume representation of the legacy well.

### Building the mesh
The generated mesh is a coarse mesh with `local grid refinement (LGR)` in the middle. The higher resolution of the LGR is used to represent well construction details.

Due to the cartesian nature of the mesh, the cylindrical shape of the well is turned into a prism. A horizontal cross-section of the well in the LGR is square, with sides meant to preserve the area of the original circle. However, discrepancies between volumes may occur due to mesh resolution.

The transport properties of geological units are inherited from coarse grid and updated to represent well. Open borehole is represented by high permeability grid cells. Cement plugs and cement-bond are represented by low permeability cells. Casing is represented by reduction of transmissibility of cell interfaces.

### Running the simulation


### Exploring the simulation output
 -->

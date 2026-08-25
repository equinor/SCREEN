# SCREEN

This repository contains source codes and documentation for SCREEN project.

[![SCREEN-unittest](https://github.com/equinor/SCREEN/actions/workflows/pytest.yaml/badge.svg)](https://github.com/equinor/SCREEN/actions/workflows/pytest.yaml)
[![SCREEN-docs](https://github.com/equinor/SCREEN/actions/workflows/mkdocs.yaml/badge.svg)](https://github.com/equinor/SCREEN/actions/workflows/mkdocs.yaml)
[![SCREEN-lint](https://github.com/equinor/SCREEN/actions/workflows/ruff.yaml/badge.svg)](https://github.com/equinor/SCREEN/actions/workflows/ruff.yaml)

## Clone the repository
Locate a folder at your local machine that you intend to investigate the codes, and then clone the repository
```
git clone https://github.com/equinor/SCREEN
```
By this time you should have a folder named `SCREEN` at your local machine. Now change the directory with linux command:
```
cd SCREEN
```

It's normal for us to make a new branch if we indend to make some changes of the codes. This can be done with the `-b` option, for example:
```
git checkout -b xyz/cleanup
```
This would generate a new branch, named `xyz/cleanup`. Here the branch name is created by concatenating a short name, such as `xyz`,  of `equinor` account with a feature description `cleanup`. There is no need to follow this convention. You could simply pick any branch name as long as it makes sense. However, please note branch names have limitations.

## Virtual environment

It's a common practice to work on a project within a python virtual environment. I have been using python's builtin module `venv` for a long while. So I am going to stick to it here as an example to set up the virtual environment. But you are free to use any other virtual environment setups that you feel comfortable with, such as `conda`, etc. 
```
python -m venv venv_screen
```
This will build a virtual environment `venv_screen`. You only need to creat it once.

To activate this `venv_screen`, run the following command: 
```
source venv_screen/bin/activate.csh
```
when your linux Shell is `csh`. 

If you are using `bash` or plain `sh`, you can activate it with the following command:
```
source venv_screen/bin/activate
```

We pack needed python packages into a file, such as `requirements.txt`. And install those python packages to this virtual environment by running the following command:
```
pip install -r requirements.txt
```
You should now be ready to play with the source codes.

## uv for dependency management
This code has been tested with Python versions 3.9 through 3.12. The recommended way to install and manage Python is using `uv`.

### 1. Installation of uv
**Equinor users:** Please follow the internal guidelines available at: https://wiki.equinor.com/wiki/Using_Python_on_Windows_11_with_uv

For Windows users, install `uv` using winget:
```
winget install --id=astral-sh.uv -e
```

For Linux/macOS users:
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Once `uv` is installed, reload your terminal and install Python:
```
uv python install 3.12
```

For other installation methods, see the [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/).

You can test that everything is set up by executing:
```
uv --version
```

### 2. Installation of python dependencies
To install python dependencies, run the following command:
```
uv sync
```

To check what packages have been installed, try the following command:
```
uv pip list
```

To show where the virtual environment is located, run:
```
uv venv --help
```
This will display information about the virtual environment. The executable path can be used in VS Code to set up python interpreter path for builtin jupyter notebooks.

The virtual environment can be activated with the command:
```
source .venv/bin/activate
```
This generated shell will be used to run standalone python scripts.

## Experiments
There are two supported ways to explore the code: the canonical Jupyter notebooks and the optional command-line experiments. The notebooks document and test the WellClass-to-GaP workflow; simulator-dependent command-line runs are intended for external-tool integration.

### 1. Jupyter notebooks
Jupyter notebooks are located in directory `notebooks`. To test its functionaries, change current directory to `notebooks` and launch jupyter notebooks at the commandline:
```
jupyter-lab
```
Or if you prefer, you can run these Jupyter notebooks from Microsoft's VS code.

The maintained, canonical notebooks are:

- **01_wellclass.ipynb** demonstrates WellClass input models, well processing, and pressure calculations.
- **02_gap_grid.ipynb** demonstrates GaP grid preparation and coarse-grid recipe generation.
- **03_wellclass_to_gap.ipynb** demonstrates the JSON-to-LGR integration workflow using an existing `.EGRID` and `.INIT` pair.
- **04_init_case_preprocessing.ipynb** demonstrates dry-run preparation of an initialization case from explicit grid assumptions.
- **05_workbook_to_cirrus_lgr.ipynb** demonstrates the selectable workbook-to-CIRRUS-to-LGR workflow for Wildcat and Smeaheia.

The notebooks in `notebooks/legacy_notebooks/` are legacy or exploratory examples. They may require external simulators, historical input formats, or additional manual setup; they are not part of the supported regression workflow. They are retained as references and sources of ideas rather than canonical entry points.

### 2. Commandline option
Two python scripts for commandline option are available in directory `experiments`. One script, **gap_pflotran.py**, can be used not only for generating Eclipse `.EGRID` and `.INIT` on the fly but also can be used for quick `pflotran` test, while the other script, **gap_wellclass.py**, requires the user to provide these two grid files.

The followings are some of  the sample runs. In either way, you should run the python script inside the ```SCREEN``` directory. 

1. To test **gap_wellclass.py**, run either of the followings:
```
# 1. for the Smeaheia GEN_NOLGR_PH2 case

python -m experiments.gap_wellclass --sim-path ./test_data/examples/smeaheia --well smeaheia.json --sim-case GEN_NOLGR_PH2 --plot

# 2. for the Smeaheia TEMP-0 case

python -m experiments.gap_wellclass --sim-path ./test_data/examples/smeaheia --well smeaheia.json --sim-case TEMP-0 --plot

# 3. for wildcat

python -m experiments.gap_wellclass --sim-path ./test_data/examples/wildcat --well wildcat.json --sim-case TEMP-0 --plot

```
This will generate an output file `LEG_HIRES.grdecl` in `experiments` directory.

2. To test **gap_pflotran.py**, run the following command from the ``SCREEN`` directory:
```python
python -m experiments.gap_pflotran \
    --sim-path ./test_data/examples/wildcat-pflotran \
    --well wildcat.yaml \
    --sim-case1 TEMP-0_NOSIM \
    --sim-case2 TEMP-0 \
    --plot
```
### 3. Test data
In order for a quick test of the codes, we include some test dataset in the folder `test_data/examples`. The input data structure is organized  similiar to the `pflotran`. For example, for test data
`test_data/examples/wildcat-pflotran-2`, the input file structure should be like this:
```
├── wildcat.yaml
├── include
│   ├── co2_db_new.dat
│   ├── temperature_gradient.inc
│   ├── TEMP_GRD.grdecl
│   ├── TEMP_GRD_NOSIM.grdecl
│   └── tops_dz.inc
└── model
    ├── TEMP-0.in
    └── TEMP-0_NOSIM.in
```
Sub-directories, such as `wildcat` and `smeaheia`, contain the necessary data, e.g., Eclipse `.EGRID` and `.INIT` files, for testing **gap_wellclass.py**. The Smeaheia folder contains both `GEN_NOLGR_PH2` and `TEMP-0` grid cases.

One sub-directory, `wildcat-plotran`, contains configuration parameters for testing **gap_pflotran.py**, i.e., use pfloatran to generate `.EGRID` and `.INIT`. 

Another sub-directory `frigg` contains information for testing deviated wells.

In addition, the **PVT** values are included in the directory `pvt_contants` for self-consistent testing of pressure-related computes.

## Unit testing and code coverage
We are using `pytest` for unit testing and code coverage. The unit testing utilizes `wildcat` as the testing example. So please make sure the saved .pkl files in ```test_data/examples/wildcat/pytest``` exists and is updated. Here is a commandline example:
```pyton
python -m pytest tests
```
This will report the unit testing results. And the following will report not only unit testing but also code coverage:
```python
python -m pytest --cov tests
```
or a litle bit more complex command:
```python
python -m pytest --cov --cov-branch --cov-report term-missing tests
```

## Documentation

The document can be automatically generated and deployed to github pages. To do that, type the following at the command line:
```
mkdocs gh-deploy
```
It may take some minutes until the documentation goes live. And the generated documentation page can be found at [SCREEN docs](https://redesigned-dollop-m5l6pme.pages.github.io/).

## The code structures

The following represents the current code structures:

```
├── experiments
│   ├── gap_pflotran.py
│   ├── gap_wellclass.py
│   ├── __init__.py
│   └── LEG_HIRES.grdecl
├── INSTALLATION.md
├── mkdocs.yml
├── notebooks
│   ├── 01_wellclass.ipynb
│   ├── 02_gap_grid.ipynb
│   ├── 03_wellclass_to_gap.ipynb
│   ├── 04_init_case_preprocessing.ipynb
│   ├── 05_workbook_to_cirrus_lgr.ipynb
│   └── legacy_notebooks
├── README.md
├── requirements.txt
├── src
│   ├── GaP
│   │   ├── data
│   │   ├── experiments
│   │   ├── __init__.py
│   │   ├── libs
│   │   ├── notebooks
│   │   └── README.md
│   ├── __init__.py
│   ├── PressCalc
│   │   ├── 1D_PresCalc.ipynb
│   │   ├── __init__.py
│   │   ├── phase_envelope.png
│   │   ├── Pressure_plot.png
│   │   ├── PT_01012996
│   │   ├── PT_010153
│   │   └── Readme.md
│   ├── WellClass
│   │   ├── __init__.py
│   │   ├── libs
│   │   ├── notebooks
│   │   └── README.md
│   └── WellViz
│       ├── __init__.py
│       ├── Readme.md
│       └── WellViz_Jan23_Dash_v4.py
└── test_data
    ├── examples
    │   ├── wildcat
    │   ├── wildcat-pflotran
    │   ├── wildcat-pflotran-2
    │   ├── frigg
    │   ├── simple_well
    │   └── smeaheia
    └── pvt_constants
        ├── pressure.txt
        ├── rho_co2.txt
        ├── rho_h2o.txt
        └── temperature.txt
```
It was generated with the linux command `tree`:
```shell
tree -I 'docs|site|venv_screen|*pycache*|Equinor*|originals' -L 3
```



""" define some fixtures
"""
import pathlib
import json
import pickle

import pytest

from src.WellClass.libs.utils import (
    csv_parser,
    yaml_parser,
)

from src.WellClass.libs.well_class import Well

# a test example: wildcat
example = {
    'sim_path': './test_data/examples/frigg',
    'well_config': 'frigg.json',
    'sim_case': 'TEMP-0.EGRID'
}

@pytest.fixture(scope='session')
def well_class_fixture():
    """ fixture for WellClass
    """

    # the paths
    sim_path = pathlib.Path(example['sim_path'])
    well_name = sim_path/example['well_config']



    # instantiate class
    my_well = Well.from_json(well_name)
    
   
    return my_well

@pytest.fixture(scope='session')
def well_class_dict_fixture():
    """ fixture for loading WellClass .pkl file for unit testing
    """
    # Define the path to the JSON file
    example_path = pathlib.Path(example['sim_path']) / example['well_config']

    # Ensure the file is JSON
    assert example_path.suffix.lower() == '.json', "Only JSON files are supported now"

    # Load JSON data from file
    with open(example_path, 'r', encoding='utf-8') as f:
        my_well_dict = json.load(f)

    return my_well_dict


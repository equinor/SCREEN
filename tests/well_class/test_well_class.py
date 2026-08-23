
from typing import List


def filter_keys(data: List[dict], keys: List[str]) -> List[dict]:
    return [{k: d[k] for k in keys if k in d} for d in data]


def test_well_header(well_class_fixture,
                     well_class_dict_fixture) -> None:
    """ test well_header
        Args:
            well_class_fixture: fixture for WellClass
            well_class_dict_fixture: fixture for WellClass example
    """

    info    = well_class_fixture.header
    info_gt = well_class_dict_fixture['spec']['well_header']

    assert info['unique_wellbore_identifier'] == info_gt['unique_wellbore_identifier']
    assert info['total_depth_rkb'] == info_gt['total_depth_rkb']

    # compare the whole dictionary
    assert info == info_gt

def test_hole_casings(well_class_fixture,
                  well_class_dict_fixture) -> None:
    """ test hole_casings
        Args:
            well_class_fixture: fixture for WellClass
            well_class_dict_fixture: fixture for WellClass example
    """
    keys_to_compare = ['name', 'type', 'top_rkb', 'bottom_rkb', 'diameter_in']

    info = filter_keys(well_class_fixture.hole_casings, keys_to_compare)
    info_gt = filter_keys(well_class_dict_fixture['spec']['hole_casings'], keys_to_compare)

    # info = well_class_fixture.hole_casings
    # info_gt = well_class_dict_fixture['spec']['hole_casings']

    # section index
    sec_index = 5

    assert info[sec_index]['diameter_in'] == info_gt[sec_index]['diameter_in']
    assert info[sec_index]['top_rkb'] == info_gt[sec_index]['top_rkb']
    assert info[sec_index]['bottom_rkb'] == info_gt[sec_index]['bottom_rkb']

    # compare the whole dictionary
    assert info == info_gt


def test_barriers(well_class_fixture,
                  well_class_dict_fixture) -> None:
    """ test barriers
        Args:
            well_class_fixture: fixture for WellClass
            well_class_dict_fixture: fixture for WellClass example
    """
    keys_to_compare = ['name', 'type', 'top_rkb', 'bottom_rkb']

    info = filter_keys(well_class_fixture.plugs, keys_to_compare)
    info_gt = filter_keys(well_class_dict_fixture['spec']['plugs'], keys_to_compare)

    # section index
    sec_index = 1

    assert info[sec_index]['name'] == info_gt[sec_index]['name']
    assert info[sec_index]['top_rkb'] == info_gt[sec_index]['top_rkb']
    assert info[sec_index]['bottom_rkb'] == info_gt[sec_index]['bottom_rkb']

    # compare the whole dictionary
    assert info == info_gt
    


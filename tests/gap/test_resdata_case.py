from pathlib import Path

import numpy as np

from src.GaP.libs.visualization import ResdataCase


def test_resdata_case_reads_committed_grid_and_init_fixture():
    case = ResdataCase(Path("test_data/examples/wildcat/model/TEMP-0"))

    assert case.dimensions == (20, 20, 60, 24000)
    assert "PORV" in case.keywords
    assert case.init_array("PORV").shape == (20, 20, 60)
    assert np.isfinite(case.cell_centers()).all()
    assert case.embedded_lgr() is None


def test_south_xz_view_has_stable_defaults():
    view = ResdataCase.south_xz_view()

    assert view == {
        "projection": "orthographic",
        "view_direction": "south",
        "plane": "xz",
        "show_coarse_grid": False,
        "vertical_scale": 0.005,
    }
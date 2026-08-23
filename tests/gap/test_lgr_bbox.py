import pandas as pd

from src.WellClass.libs.grid_utils.LGR_bbox import (
    compute_bbox,
    get_ij_indices,
    get_k_indices,
)


def make_mesh():
    return pd.DataFrame(
        {
            "k": [0, 1, 2],
            "Zcorn_top": [0.0, 10.0, 20.0],
            "Zcorn_bottom": [10.0, 20.0, 30.0],
        }
    )


def test_k_indices_handle_cell_edges_and_grid_limits():
    mesh = make_mesh()

    assert get_k_indices(mesh, 0.0, 10.0) == (0, 0)
    assert get_k_indices(mesh, 10.0, 20.0) == (1, 1)
    assert get_k_indices(mesh, -5.0, 40.0) == (0, 2)


def test_ij_indices_center_the_requested_well_width():
    assert get_ij_indices(nxy=10, n_grd=4) == (3, 6)
    assert get_ij_indices(nxy=11, n_grd=4) == (3, 6)


def test_compute_bbox_adds_casing_and_cement_indices():
    mesh = make_mesh()
    casings = pd.DataFrame(
        [
            {
                "top_msl": 10.0,
                "bottom_msl": 20.0,
                "toc_msl": 10.0,
                "boc_msl": 20.0,
                "n_grd_id": 4,
            }
        ]
    )

    compute_bbox(mesh, casings, nxy=10, is_casing=True)

    assert casings.loc[0, ["k_min", "k_max"]].tolist() == [1, 1]
    assert casings.loc[0, ["ij_min", "ij_max"]].tolist() == [3, 6]
    assert casings.loc[0, ["toc_k_min", "toc_k_max"]].tolist() == [1, 1]
import itertools

import pandas as pd

from src.WellClass.libs.grid_utils.grid_refine_base import GridRefineBase


def make_refine_stub():
    mesh = []
    for i, j, k in itertools.product(range(3), repeat=3):
        mesh.append(
            {
                "i": i,
                "j": j,
                "k": k,
                "Zcorn_top": float(k * 10),
                "Zcorn_bottom": float((k + 1) * 10),
            }
        )

    refine = GridRefineBase.__new__(GridRefineBase)
    refine.mesh_df = pd.DataFrame(mesh)
    refine.nx = 3
    refine.min_grd_size = 0.05
    return refine


def make_sections():
    drilling = pd.DataFrame(
        [{"top_msl": 0.0, "bottom_msl": 30.0, "k_min": 0, "k_max": 2, "ij_min": 0, "ij_max": 2, "oh_perm": 10000.0}]
    )
    casing = pd.DataFrame(
        [{"k_min": 0, "k_max": 1, "ij_min": 1, "ij_max": 1, "toc_k_min": 0, "toc_k_max": 0, "cb_perm": 0.05}]
    )
    barriers = pd.DataFrame(
        [{"k_min": 1, "k_max": 1, "diameter_m": 0.2, "barrier_perm": 0.001}]
    )
    return drilling, casing, barriers


def test_material_assignment_preserves_cement_and_barrier_regions():
    refine = make_refine_stub()
    drilling, casing, barriers = make_sections()

    refine._set_material_type(drilling, casing, barriers)

    center = refine.mesh_df.query("i == 1 and j == 1")
    assert center.query("k == 0").iloc[0]["material"] == "openhole"
    assert center.query("k == 1").iloc[0]["material"] == "barrier_0"
    assert refine.mesh_df.query("material == 'cement_bond_0'").shape[0] > 0


def test_permeability_follows_assigned_material():
    refine = make_refine_stub()
    drilling, casing, barriers = make_sections()

    refine._set_material_type(drilling, casing, barriers)
    refine._set_permeability(drilling, casing, barriers)

    center = refine.mesh_df.query("i == 1 and j == 1")
    assert center.query("k == 0").iloc[0]["PERMX"] == 10000.0
    assert center.query("k == 1").iloc[0]["PERMX"] == 0.001
    assert refine.mesh_df.query("material == 'cement_bond_0'").iloc[0]["PERMX"] == 0.05
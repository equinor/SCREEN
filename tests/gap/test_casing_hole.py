from io import StringIO
from math import pi, sqrt
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError
from resdata.grid import Grid

from src.GaP.libs.grid_utils.casing_hole import refined_depth_edges, resolve_casing_hole, write_casing_hole
from src.GaP.libs.models.casing_hole import CasingHole
from src.GaP.libs.models.simulation_scenario import SimulationScenario
from src.WellClass.libs.grid_utils import LGRBuilder, WellDataFrame
from src.WellClass.libs.well_class import WellProcessed


def _hole(area=0.5, depth=12.0, casing="target"):
    return CasingHole(casing=casing, depth_mTVDMSL=depth, diameter_m=sqrt(4 * area / pi))


def _casings():
    return pd.DataFrame(
        [{"name": "target", "top_msl": 10.0, "bottom_msl": 16.0, "ij_min": 1, "ij_max": 3, "k_min": 0, "k_max": 2}]
    )


def _resolve(hole, casings=None):
    return resolve_casing_hole(
        hole, _casings() if casings is None else casings,
        np.array([10.0, 12.0, 14.0, 16.0]), np.full(5, 0.5), 5,
    )


def test_absent_hole_preserves_defaults_and_writer_output():
    assert SimulationScenario().casing_hole is None
    stream = StringIO("unchanged")
    stream.seek(0, 2)
    write_casing_hole((), stream)
    assert stream.getvalue() == "unchanged"


@pytest.mark.parametrize(
    "fields",
    [
        {"casing_hole_casing": "target"},
        {"casing_hole_depth_mTVDMSL": 12.0},
        {"casing_hole_diameter_m": 0.1},
        {"casing_hole_casing": "target", "casing_hole_depth_mTVDMSL": 12.0},
        {"casing_hole_casing": "target", "casing_hole_diameter_m": 0.1},
        {"casing_hole_depth_mTVDMSL": 12.0, "casing_hole_diameter_m": 0.1},
        {"casing_hole_casing": "", "casing_hole_depth_mTVDMSL": 12.0, "casing_hole_diameter_m": 0.1},
        {"casing_hole_casing": "target", "casing_hole_depth_mTVDMSL": float("nan"), "casing_hole_diameter_m": 0.1},
        {"casing_hole_casing": "target", "casing_hole_depth_mTVDMSL": float("inf"), "casing_hole_diameter_m": 0.1},
        {"casing_hole_casing": "target", "casing_hole_depth_mTVDMSL": 12.0, "casing_hole_diameter_m": 0},
        {"casing_hole_casing": "target", "casing_hole_depth_mTVDMSL": 12.0, "casing_hole_diameter_m": -1},
        {"casing_hole_casing": "target", "casing_hole_depth_mTVDMSL": 12.0, "casing_hole_diameter_m": float("inf")},
        {"casing_hole_casing": "target", "casing_hole_depth_mTVDMSL": 12.0, "casing_hole_diameter_m": float("nan")},
    ],
)
def test_invalid_scenario_hole_fields(fields):
    with pytest.raises(ValidationError):
        SimulationScenario(**fields)


@pytest.mark.parametrize("depth,expected_k", [(10, 1), (11.999, 1), (12, 2), (15.999, 3)])
def test_single_face_and_boundary_depth_ownership(depth, expected_k):
    faces = _resolve(_hole(depth=depth))
    assert len(faces) == 1
    face = faces[0]
    assert (face.i, face.j, face.k) == (4, 3, expected_k)
    assert face.face_area_m2 == 1
    assert face.multiplier == pytest.approx(0.5)
    assert face.opening_area_m2 == pytest.approx(pi * (_hole().diameter_m / 2) ** 2)


def test_large_hole_spreads_only_along_y_in_same_layer():
    exact_face = _resolve(_hole(area=1))
    assert len(exact_face) == 1
    assert exact_face[0].multiplier == pytest.approx(1)
    faces = _resolve(_hole(area=2.5))
    assert [(face.i, face.j, face.k) for face in faces] == [(4, 3, 2), (4, 2, 2), (4, 4, 2)]
    assert [face.multiplier for face in faces] == pytest.approx([1, 1, 0.5])
    assert sum(face.opening_area_m2 for face in faces) == pytest.approx(2.5, rel=1e-12)
    assert all(0 < face.multiplier <= 1 for face in faces)
    assert len(_resolve(_hole(area=3))) == 3
    with pytest.raises(ValueError, match="exceeds"):
        _resolve(_hole(area=3.1))


def test_even_side_uses_lower_j_midpoint_face_first():
    casings = _casings()
    casings["ij_max"] = 2
    assert _resolve(_hole(), casings)[0].j == 2


def test_nonuniform_side_uses_physical_midpoint_and_each_face_area():
    widths = np.array([1.0, 0.25, 1.0, 2.0, 1.0])
    faces = resolve_casing_hole(
        _hole(area=5), _casings(), np.array([10.0, 12.0, 14.0, 16.0]), widths, 5,
    )
    assert [face.j for face in faces] == [4, 3]
    assert [face.face_area_m2 for face in faces] == [4, 2]
    assert [face.multiplier for face in faces] == pytest.approx([1, 0.5])
    assert sum(face.opening_area_m2 for face in faces) == pytest.approx(5)


@pytest.mark.parametrize("depth", [9.999, 16, 17])
def test_depth_outside_casing_is_rejected(depth):
    with pytest.raises(ValueError, match="inside"):
        _resolve(_hole(depth=depth))


def test_missing_duplicate_shared_and_outer_boundary_interfaces_are_rejected():
    with pytest.raises(ValueError, match="exactly one"):
        _resolve(_hole(casing="missing"))
    with pytest.raises(ValueError, match="exactly one"):
        _resolve(_hole(), pd.concat([_casings(), _casings()]))
    with pytest.raises(ValueError, match="shared"):
        _resolve(_hole(), pd.concat([_casings(), _casings().assign(name="other")]))
    with pytest.raises(ValueError, match="adjacent"):
        _resolve(_hole(), _casings().assign(ij_max=4))


def test_real_grid_depth_edges_include_nonzero_origin():
    root = Path(__file__).parents[2]
    grid = Grid(str(root / "test_data/examples/wildcat/model/TEMP-0.EGRID"))
    edges = refined_depth_edges(grid, 9, 9, np.array([10, 10]))
    assert edges[[0, 10, 20]] == pytest.approx([4, 105, 248])
    assert np.diff(edges)[:10] == pytest.approx(np.full(10, 10.1))
    assert refined_depth_edges(grid, 9, 9, np.array([10]), first_k=1)[[0, 10]] == pytest.approx([105, 248])


@pytest.mark.parametrize("count", [0, -1, 1.5, float("nan")])
def test_invalid_refinement_counts_are_rejected(count):
    root = Path(__file__).parents[2]
    grid = Grid(str(root / "test_data/examples/wildcat/model/TEMP-0.EGRID"))
    with pytest.raises(ValueError, match="positive integers"):
        refined_depth_edges(grid, 9, 9, np.array([count]))


@pytest.mark.parametrize("distortion", ["slope", "gap", "taper", "shear"])
def test_unsupported_grid_geometry_is_rejected(monkeypatch, distortion):
    root = Path(__file__).parents[2]
    grid = Grid(str(root / "test_data/examples/wildcat/model/TEMP-0.EGRID"))
    original_corner = grid.get_cell_corner

    def distorted_corner(corner, *, ijk):
        x, y, z = original_corner(corner, ijk=ijk)
        if distortion == "slope" and corner == 1:
            z += 0.1
        if distortion == "gap" and ijk[2] == 1:
            z += 1
        if distortion == "taper" and corner >= 4:
            x += 1
        if distortion == "shear" and corner in (2, 3, 6, 7):
            x += 1
        return x, y, z

    monkeypatch.setattr(grid, "get_cell_corner", distorted_corner)
    with pytest.raises(ValueError, match="require"):
        refined_depth_edges(grid, 9, 9, np.array([10, 10]))


def test_builder_changes_only_selected_multiplier_records(tmp_path):
    root = Path(__file__).parents[2]
    fixture = root / "test_data/examples/wildcat"
    outputs = []
    meshes = []
    frames = []
    for hole in (None, CasingHole(casing="Casing 20 in", depth_mTVDMSL=200, diameter_m=0.1)):
        well = WellProcessed.from_json(fixture / "wildcat.json")
        frame = WellDataFrame(well, oh_perm=10000.0, cb_perm=0.05, barrier_perm=0.05)
        builder = LGRBuilder(str(fixture / "model/TEMP-0"), frame.annulus_df, frame.holes_df, False)
        builder.build_grdecl(
            str(tmp_path), "TEMP_LGR", frame.holes_df, frame.casings_df, frame.barrier_regions_df, casing_hole=hole
        )
        outputs.append((tmp_path / "TEMP_LGR.grdecl").read_text())
        meshes.append(builder.grid_refine.mesh_df.copy(deep=True))
        frames.append(frame.casings_df.copy(deep=True))
    pd.testing.assert_frame_equal(meshes[0], meshes[1])
    pd.testing.assert_frame_equal(frames[0], frames[1])
    stream = StringIO()
    write_casing_hole(builder.casing_hole_faces, stream)
    override = stream.getvalue()
    assert outputs[1].replace(override, "") == outputs[0]
    assert outputs[1].count(override) == 1
    lines = outputs[1].splitlines()
    seal_lines = [index for index, line in enumerate(lines) if line.startswith("MULTX") and float(line.split()[1]) == 0]
    assert lines.index(override.splitlines()[0]) > max(seal_lines)
    face = builder.casing_hole_faces[0]
    assert (face.i, face.j, face.k) == (15, 11, 17)
    assert face.face_area_m2 == pytest.approx(face.opening_area_m2 / face.multiplier)
    assert face.opening_area_m2 == pytest.approx(pi * 0.05**2)
    hyfin = np.asarray([float(value) for value in outputs[1].split("HYFIN\n")[1].split("/")[0].split()])
    assert face.face_area_m2 == pytest.approx(hyfin[face.j - 1] / hyfin.sum() * 200 * 14.3)
    sealed_faces = [lines[index].split() for index in seal_lines]
    assert any(
        int(record[2]) <= face.i <= int(record[3])
        and int(record[4]) <= face.j <= int(record[5])
        and int(record[6]) <= face.k <= int(record[7])
        for record in sealed_faces
    )

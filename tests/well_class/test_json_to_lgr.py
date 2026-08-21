from pathlib import Path

import numpy as np
import pytest

from src.WellClass.libs.grid_utils import LGRBuilder, WellDataFrame
from src.WellClass.libs.well_class import WellProcessed


@pytest.mark.parametrize(
    ("well_name", "grid_case", "coarse_dimensions", "refined_dimensions", "expected_casing_perm"),
    [
        ("wildcat", "TEMP-0", (20, 20, 60), (22, 22, 150), 0.05),
        ("smeaheia", "TEMP-0", (20, 20, 60), (22, 22, 150), 5.0),
        ("smeaheia", "GEN_NOLGR_PH2", (20, 20, 82), (22, 22, 172), 5.0),
    ],
    ids=["wildcat-TEMP-0", "smeaheia-TEMP-0", "smeaheia-GEN_NOLGR_PH2"],
)
def test_json_builds_reviewable_lgr_grdecl(
    tmp_path, well_name, grid_case, coarse_dimensions, refined_dimensions, expected_casing_perm
):
    root = Path(__file__).parents[2]
    fixture_root = root / "test_data/examples" / well_name
    well = WellProcessed.from_json(fixture_root / f"{well_name}.json")
    frames = WellDataFrame(well, oh_perm=10000.0, cb_perm=0.05, barrier_perm=0.05)

    builder = LGRBuilder(
        str(fixture_root / "model" / grid_case),
        frames.annulus_df,
        frames.holes_df,
        False,
    )

    assert (builder.grid_coarse.NX, builder.grid_coarse.NY, builder.grid_coarse.NZ) == coarse_dimensions
    assert (builder.grid_refine.nx, builder.grid_refine.ny, builder.grid_refine.nz) == refined_dimensions
    assert np.isfinite(builder.grid_refine.mesh_df[["PERMX", "PERMY", "PERMZ"]].to_numpy()).all()
    assert (builder.grid_refine.mesh_df[["PERMX", "PERMY", "PERMZ"]] >= 0).all().all()
    assert np.isclose(frames.casings_df["cb_perm"].dropna(), expected_casing_perm).any()

    output_name = f"{well_name.upper()}_{grid_case}_LGR"
    builder.build_grdecl(
        str(tmp_path),
        output_name,
        frames.holes_df,
        frames.casings_df,
        frames.barrier_regions_df,
    )
    output_file = tmp_path / f"{output_name}.grdecl"
    assert output_file.exists()

    output = output_file.read_text(encoding="utf-8")
    assert f"CARFIN\n{output_name}" in output
    assert "NXFIN\n22 /" in output
    assert "NYFIN\n22 /" in output
    assert "NZFIN\n" in output
    assert "PERMX" in output
    assert "PERMY" in output
    assert "PERMZ" in output
    assert "10000.0" in output
    assert str(expected_casing_perm) in output
    assert output.rstrip().endswith("ENDFIN")
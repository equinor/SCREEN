from pathlib import Path

import numpy as np

from src.WellClass.libs.grid_utils import LGRBuilder, WellDataFrame
from src.WellClass.libs.well_class import WellProcessed


def test_wildcat_json_builds_reviewable_lgr_grdecl(tmp_path):
    root = Path(__file__).parents[2]
    well = WellProcessed.from_json(root / "test_data/examples/wildcat/wildcat.json")
    frames = WellDataFrame(well, oh_perm=10000.0, cb_perm=0.05, barrier_perm=0.05)

    builder = LGRBuilder(
        str(root / "test_data/examples/wildcat/model/TEMP-0"),
        frames.annulus_df,
        frames.holes_df,
        False,
    )

    assert (builder.grid_coarse.NX, builder.grid_coarse.NY, builder.grid_coarse.NZ) == (20, 20, 60)
    assert (builder.grid_refine.nx, builder.grid_refine.ny, builder.grid_refine.nz) == (22, 22, 150)
    assert np.isfinite(builder.grid_refine.mesh_df[["PERMX", "PERMY", "PERMZ"]].to_numpy()).all()
    assert (builder.grid_refine.mesh_df[["PERMX", "PERMY", "PERMZ"]] >= 0).all().all()

    builder.build_grdecl(
        str(tmp_path),
        "WILDCAT_LGR",
        frames.holes_df,
        frames.casings_df,
        frames.barrier_regions_df,
    )
    output_file = tmp_path / "WILDCAT_LGR.grdecl"
    assert output_file.exists()

    output = output_file.read_text(encoding="utf-8")
    assert "CARFIN\nWILDCAT_LGR" in output
    assert "NXFIN\n22 /" in output
    assert "NYFIN\n22 /" in output
    assert "NZFIN\n" in output
    assert "PERMX" in output
    assert "PERMY" in output
    assert "PERMZ" in output
    assert "10000.0" in output
    assert "0.05" in output
    assert output.rstrip().endswith("ENDFIN")
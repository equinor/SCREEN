from io import StringIO
from pathlib import Path

import pandas as pd

from src.GaP.libs.grid_utils.wellbore_porv import write_wellbore_porv_reset
from src.WellClass.libs.grid_utils import LGRBuilder, WellDataFrame
from src.WellClass.libs.well_class import WellProcessed


def _holes():
    return pd.DataFrame(
        [
            {"ij_min": 8, "ij_max": 13, "k_min": 0, "k_max": 79},
            {"ij_min": 9, "ij_max": 12, "k_min": 80, "k_max": 149},
        ]
    )


def test_reset_divides_pore_volume_on_the_open_hole_cells_of_the_last_layer_only():
    stream = StringIO()
    write_wellbore_porv_reset(_holes(), 150, 2000.0, stream)
    assert stream.getvalue().splitlines() == [
        "-- SCREEN: undo the inherited bottom-layer pore volume multiplier on the open-hole cells",
        "MULTIPLY",
        "PORV 0.0005 10 13 10 13 150 150 /",
        "/",
    ]


def test_reset_writes_nothing_without_a_bottom_open_hole_or_a_multiplier():
    for holes, layers, multiplier in ((_holes(), 160, 2000.0), (_holes(), 150, 1.0), (_holes().iloc[:1], 150, 2000.0)):
        stream = StringIO()
        write_wellbore_porv_reset(holes, layers, multiplier, stream)
        assert stream.getvalue() == ""


def test_builder_adds_only_the_reset_block(tmp_path):
    fixture = Path(__file__).parents[2] / "test_data/examples/wildcat"
    outputs = []
    for reset in (None, 2000.0):
        (tmp_path / str(reset)).mkdir()
        frame = WellDataFrame(WellProcessed.from_json(fixture / "wildcat.json"), oh_perm=10000.0, cb_perm=0.05, barrier_perm=0.05)
        builder = LGRBuilder(str(fixture / "model/TEMP-0"), frame.annulus_df, frame.holes_df, False)
        builder.build_grdecl(
            str(tmp_path / str(reset)), "TEMP_LGR", frame.holes_df, frame.casings_df, frame.barrier_regions_df, wellbore_porv_reset=reset
        )
        outputs.append((tmp_path / str(reset) / "TEMP_LGR.grdecl").read_text())
    block = "-- SCREEN: undo the inherited bottom-layer pore volume multiplier on the open-hole cells\nMULTIPLY\nPORV 0.0005 9 14 9 14 150 150 /\n/\n"
    assert outputs[1].replace(block, "") == outputs[0]
    assert outputs[1].count(block) == 1

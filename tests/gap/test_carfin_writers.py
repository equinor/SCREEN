from io import StringIO

import numpy as np

from src.GaP.libs.carfin.CARFIN_barrier import CARFIN_barrier
from src.GaP.libs.carfin.CARFIN_cement_bond import CARFIN_cement_bond
from src.GaP.libs.carfin.CARFIN_core import CARFIN_keywords, pre_CARFIN
from src.GaP.libs.carfin.CARFIN_oph import CARFIN_oph
from src.GaP.libs.carfin.CARFIN_pipe_with_oph import CARFIN_pipe_with_oph


def test_open_hole_writer_emits_properties_and_closes_equals_block():
    output = StringIO()

    CARFIN_oph(0.3, 2, 4, 2, 4, 5, 8, 1000.0, "TEST", output)
    text = output.getvalue()

    assert "PERMX  1000.0  2  4  2  4  5  8  /" in text
    assert "SATNUM  2  2  4  2  4  5  8  /" in text
    assert text.rstrip().endswith("/")


def test_pipe_writer_emits_open_hole_and_edge_transmissibility():
    output = StringIO()

    CARFIN_pipe_with_oph(0.3, 2, 4, 2, 4, 5, 8, 6, 9, 1000.0, "TEST", output)
    text = output.getvalue()

    assert "PERMX  1000.0  2  4  2  4  6  9  /" in text
    assert "MULTX  0  1  1  2  4  5  8  /" in text
    assert "MULTY  0  1  4  1  1  5  8  /" in text
    assert text.rstrip().endswith("/")


def test_cement_and_barrier_writers_emit_expected_regions():
    cement_output = StringIO()
    barrier_output = StringIO()

    CARFIN_cement_bond(
        0.3,
        2,
        4,
        2,
        4,
        5,
        8,
        x_bd=1,
        y_bd=2,
        perm=0.05,
        LGR_NAME="TEST",
        O=cement_output,
    )
    CARFIN_barrier(0.3, 2, 4, 2, 4, 10, 12, 0.001, "TEST", barrier_output)

    cement_text = cement_output.getvalue()
    barrier_text = barrier_output.getvalue()
    assert "--Top side" in cement_text
    assert "PERMX  0.05  1  5  0  1  5  8  /" in cement_text
    assert "PERMX  0.001  2  4  2  4  10  12  /" in barrier_text
    assert cement_text.rstrip().endswith("/")
    assert barrier_text.rstrip().endswith("/")


def test_core_writers_emit_lgr_setup_keywords():
    output = StringIO()

    pre_CARFIN("TEST", 20, 20, 10, 10, 9, output)
    CARFIN_keywords("TEST", 10, 10, 0, 59, [1.0, 0.5], np.array([10, 1]), 0.05, output)
    text = output.getvalue()

    assert "MULTZ  0  1  20 1  20 9 9 /" in text
    assert "CARFIN\nTEST" in text
    assert "NXFIN" in text
    assert text.count("EQUALS") == 1
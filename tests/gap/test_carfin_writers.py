from io import StringIO

import numpy as np
import pytest

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
    assert "MULTY  0  2  4  1  1  5  8  /" in text
    assert text.rstrip().endswith("/")


@pytest.mark.parametrize("bounds", [(2, 4, 2, 4), (3, 6, 8, 9), (2, 2, 3, 3)])
def test_pipe_multipliers_block_exactly_the_casing_perimeter(bounds):
    imin, imax, jmin, jmax = bounds
    output = StringIO()
    CARFIN_pipe_with_oph(0.3, *bounds, 5, 8, 5, 10, 1000.0, "TEST", output)
    blocked = {"MULTX": set(), "MULTY": set()}
    for line in output.getvalue().splitlines():
        record = line.split()
        if record and record[0] in blocked:
            assert float(record[1]) == 0
            i0, i1, j0, j1, k0, k1 = map(int, record[2:8])
            blocked[record[0]].update(
                (i, j, k)
                for i in range(i0, i1 + 1)
                for j in range(j0, j1 + 1)
                for k in range(k0, k1 + 1)
            )
    assert blocked["MULTX"] == {
        (i, j, k) for i in (imin - 1, imax)
        for j in range(jmin, jmax + 1) for k in range(5, 9)
    }
    assert blocked["MULTY"] == {
        (i, j, k) for i in range(imin, imax + 1)
        for j in (jmin - 1, jmax) for k in range(5, 9)
    }
    # Every blocked face must separate a pipe cell from a non-pipe cell.
    def inside(i, j):
        return imin <= i <= imax and jmin <= j <= jmax
    for name, (di, dj) in (("MULTX", (1, 0)), ("MULTY", (0, 1))):
        assert all(
            inside(i, j) != inside(i + di, j + dj)
            for i, j, _ in blocked[name]
        )


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
    assert "SATNUM  1  1  5  0  1  5  8  /" in cement_text
    assert "SATNUM  1  1  5  5  6  5  8  /" in cement_text
    assert "SATNUM  1  1  1  2  4  5  8  /" in cement_text
    assert "SATNUM  1  5  5  2  4  5  8  /" in cement_text
    assert "PERMX  0.001  2  4  2  4  10  12  /" in barrier_text
    assert "SATNUM  1  2  4  2  4  10  12  /" in barrier_text
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
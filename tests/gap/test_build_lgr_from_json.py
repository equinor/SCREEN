from pathlib import Path
import subprocess
import sys
import pytest


@pytest.mark.parametrize("with_hole", [False, True])
def test_build_lgr_from_json_writes_carfin(tmp_path, with_hole):
    root = Path(__file__).parents[2]
    output_path = tmp_path / "TEST_LGR.grdecl"
    if not with_hole:
        output_path.with_suffix(".casing_hole.json").write_text('{"stale": true}')
    subprocess.run(
        [
            "uv",
            "run",
            "python",
            "runscripts/build_lgr_from_json.py",
            "--well-json",
            "test_data/examples/wildcat/wildcat.json",
            "--sim-case",
            "test_data/examples/wildcat/model/TEMP-0",
            "--output-folder",
            str(tmp_path),
            "--lgr-name",
            "TEST_LGR",
        ] + (
            [
                "--casing-hole-casing", "Casing 20 in",
                "--casing-hole-depth-mTVDMSL", "200",
                "--casing-hole-diameter-m", "0.1",
            ] if with_hole else []
        ),
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    content = output_path.read_text(encoding="utf-8")
    assert "CARFIN" in content
    assert "TEST_LGR" in content
    assert ("SCREEN experimental casing hole" in content) == with_hole
    assert output_path.with_suffix(".casing_hole.json").exists() == with_hole


def test_build_lgr_restricts_co2_region_after_deepest_plug(tmp_path):
    root = Path(__file__).parents[2]
    output_path = tmp_path / "TEST_LGR.grdecl"
    subprocess.run(
        [
            "uv",
            "run",
            "python",
            "runscripts/build_lgr_from_json.py",
            "--well-json",
            "test_data/examples/smeaheia/smeaheia.json",
            "--sim-case",
            "test_data/examples/smeaheia/model/TEMP-0",
            "--output-folder",
            str(tmp_path),
            "--lgr-name",
            "TEST_LGR",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    eqlnum_two = [line for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip().startswith("EQLNUM  2")]
    assert eqlnum_two
    assert all(int(line.split()[6]) >= 85 for line in eqlnum_two)


def _run_builder(tmp_path, *extra):
    root = Path(__file__).parents[2]
    return subprocess.run(
        [
            sys.executable, "runscripts/build_lgr_from_json.py",
            "--well-json", "test_data/examples/wildcat/wildcat.json",
            "--sim-case", "test_data/examples/wildcat/model/TEMP-0",
            "--output-folder", str(tmp_path), "--lgr-name", "TEST_LGR", *extra,
        ],
        cwd=root, capture_output=True, text=True,
    )


def test_free_fluid_properties_reach_pipe_and_open_hole_cells(tmp_path):
    result = _run_builder(tmp_path, "--free-fluid-permx", "5000", "--free-fluid-poro", "0.9")
    assert result.returncode == 0, result.stderr
    lines = (tmp_path / "TEST_LGR.grdecl").read_text(encoding="utf-8").splitlines()
    assert "PERMX  5000.0  6  17  6  17  11  13  /" in lines
    assert "PORO  0.9  9  14  9  14  83  150  /" in lines
    assert not [line for line in lines if line.startswith("PORO  0.99") or "10000.0" in line]


def test_default_free_fluid_properties(tmp_path):
    assert _run_builder(tmp_path).returncode == 0
    lines = (tmp_path / "TEST_LGR.grdecl").read_text(encoding="utf-8").splitlines()
    assert "PERMX  10000.0  9  14  9  14  83  150  /" in lines
    assert "PORO  1.0  9  14  9  14  83  150  /" in lines


def test_oh_perm_is_deprecated_and_cannot_conflict(tmp_path):
    result = _run_builder(tmp_path, "--oh-perm", "5000")
    assert result.returncode == 0, result.stderr
    assert "--oh-perm is deprecated" in result.stderr
    assert "PERMX  5000.0  9  14  9  14  83  150  /" in (tmp_path / "TEST_LGR.grdecl").read_text(encoding="utf-8")

    conflict = _run_builder(tmp_path, "--oh-perm", "5000", "--free-fluid-permx", "7000")
    assert conflict.returncode != 0
    assert "conflicts with the free-fluid permeability 7000 mD" in conflict.stderr

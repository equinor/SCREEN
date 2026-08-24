from pathlib import Path
import subprocess


def test_build_lgr_from_json_writes_carfin(tmp_path):
    root = Path(__file__).parents[2]
    output_path = tmp_path / "TEST_LGR.grdecl"
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
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    content = output_path.read_text(encoding="utf-8")
    assert "CARFIN" in content
    assert "TEST_LGR" in content

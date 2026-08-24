from pathlib import Path
import subprocess
import sys

import pandas as pd

from src.WellClass.libs.utils.xlsx_parser import xlsx_grid_policy


def _write_minimal_workbook(path: Path) -> None:
    metadata = pd.DataFrame({"key": ["namespace", "name", "author"], "value": ["screen", "xlsx-test", "pytest"]})
    header = pd.DataFrame(
        {
            "key": [
                "unique_wellbore_identifier",
                "depth_reference_rkb",
                "depth_reference_rkb_unit",
                "ground_elevation",
                "ground_elevation_unit",
                "total_depth_rkb",
                "total_depth_rkb_unit",
            ],
            "value": ["NO 00/0-0", 27, "m", 105, "m", 3997, "m"],
        }
    )
    grid_policy = pd.DataFrame(
        {
            "key": [
                "top_depth",
                "water_depth",
                "reservoir_top",
                "bottom_depth",
                "target_dz_water",
                "target_dz_overburden",
                "target_dz_reservoir",
                "cells_per_layer",
            ],
            "value": [4.0, 104.0, 1004.0, 1504.0, 50.0, 60.0, 10.0, 400],
        }
    )

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        metadata.to_excel(writer, sheet_name="Metadata", index=False)
        header.to_excel(writer, sheet_name="Header", index=False)
        grid_policy.to_excel(writer, sheet_name="GridPolicy", index=False)


def test_prepare_init_case_from_xlsx_stages_files(tmp_path):
    workbook = tmp_path / "well_input.xlsx"
    _write_minimal_workbook(workbook)

    output_root = tmp_path / "staged_case"
    repo_root = Path(__file__).parents[2]

    command = [
        sys.executable,
        "runscripts/prepare_init_case_from_xlsx.py",
        "--xlsx",
        str(workbook),
        "--output-root",
        str(output_root),
        "--write-well-json",
    ]
    subprocess.run(command, check=True, cwd=repo_root, capture_output=True, text=True)

    deck = output_root / "model" / "TEMP-0.in"
    grdecl = output_root / "include" / "TEMP_GRD.grdecl"
    co2_database = output_root / "include" / "co2_db_new.dat"
    tops = output_root / "include" / "tops_dz.inc"
    well_json = output_root / "well_input.json"

    assert deck.exists()
    assert grdecl.exists()
    assert co2_database.exists()
    assert tops.exists()
    assert well_json.exists()

    recipe = tops.read_text(encoding="utf-8")
    assert "TOPS 4" in recipe
    assert "800*50" in recipe
    assert "6000*60" in recipe
    assert "20000*10" in recipe
    assert "DATABASE ../include/co2_db_new.dat" in deck.read_text(encoding="utf-8")


def test_xlsx_grid_policy_requires_keys(tmp_path):
    workbook = tmp_path / "bad_policy.xlsx"
    header = pd.DataFrame({"key": ["unique_wellbore_identifier"], "value": ["NO 00/0-0"]})
    policy = pd.DataFrame({"key": ["top_depth"], "value": [4.0]})
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        header.to_excel(writer, sheet_name="Header", index=False)
        policy.to_excel(writer, sheet_name="GridPolicy", index=False)

    try:
        xlsx_grid_policy(workbook)
    except ValueError as exc:
        assert "missing required keys" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing GridPolicy keys")

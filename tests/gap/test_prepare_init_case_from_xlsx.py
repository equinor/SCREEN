from pathlib import Path
import subprocess
import sys

from openpyxl import load_workbook
import pandas as pd
import pytest

from src.WellClass.libs.utils.xlsx_parser import xlsx_grid_policy, xlsx_to_simulation_design, xlsx_to_well_model


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
                "target_dz_water",
                "target_dz_overburden",
                "target_dz_reservoir",
                "reservoir_permx",
                "overburden_permx",
                "cells_per_layer",
            ],
            "value": [4.0, 50.0, 60.0, 10.0, 1000.0, 0.001, 400],
        }
    )

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        metadata.to_excel(writer, sheet_name="Metadata", index=False)
        header.to_excel(writer, sheet_name="Header", index=False)
        grid_policy.to_excel(writer, sheet_name="GridPolicy", index=False)
        pd.DataFrame(
            {
                "temperature_gradient": [31.0],
                "ground_temperature": [4.0],
                "z_fluid_contact": [2400.0],
                "p_fluid_contact": [210.0],
                "overburden_datum_depth": [500.0],
                "z_resrv": [1400.0],
                "p_resrv": [250.0],
            }
        ).to_excel(writer, sheet_name="SubsurfaceAssumptions", index=False)
        pd.DataFrame(
            {
                "name": ["RESERVOIR"],
                "top_rkb": [1027.0],
                "bottom_rkb": [1400.0],
                "unit_type": ["reservoir"],
            }
        ).to_excel(writer, sheet_name="Stratigraphy", index=False)
        pd.DataFrame(
            {
                "name": ["Hole"],
                "type": ["hole"],
                "top_rkb": [444.0],
                "bottom_rkb": [1812.0],
                "diameter_in": [17.5],
                "shoe": [False],
            }
        ).to_excel(writer, sheet_name="HoleCasings", index=False)


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
    assert "1200*33.6667" in recipe
    assert "6000*59.6667" in recipe
    assert "16000*10" in recipe
    assert "DATABASE ../include/co2_db_new.dat" in deck.read_text(encoding="utf-8")
    assert "TEMP_LGR.grdecl" not in grdecl.read_text(encoding="utf-8")
    grdecl_text = grdecl.read_text(encoding="utf-8")
    assert "EQLNUM 1 1 20 1 20 1 18 /" in grdecl_text
    assert "EQLNUM 2 1 20 1 20 19 58 /" in grdecl_text
    assert "PERMX 10000 1 20 1 20 1 3 /" in grdecl_text
    assert "PERMX 0.001 1 20 1 20 4 18 /" in grdecl_text
    assert "PORO 1 1 20 1 20 1 3 /" in grdecl_text
    assert "FIPLEG 3 1 20 1 20 19 55 /" in grdecl_text
    assert "FIPLEG 5 1 20 1 20 56 58 /" in grdecl_text
    assert "PERMX 1000 1 20 1 20 56 58 /" in grdecl_text
    assert "TRANZ 0 1 20 1 20 19 19 /" in grdecl_text
    assert "PERMZ 0.1 1 20 1 20 4 58 /" in grdecl_text


def test_workbook_keeps_simulation_assumptions_outside_well_model(tmp_path):
    workbook = tmp_path / "well_input.xlsx"
    _write_minimal_workbook(workbook)

    well_model = xlsx_to_well_model(workbook)
    scenario = xlsx_to_simulation_design(workbook).select()

    assert well_model.spec.subsurface_assumptions is None
    assert scenario.z_fluid_contact == 2400.0
    assert scenario.p_fluid_contact == 210.0


def test_prepare_init_case_from_xlsx_configures_final_run(tmp_path):
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
        "--final-run",
    ]
    subprocess.run(command, check=True, cwd=repo_root, capture_output=True, text=True)

    deck = (output_root / "model" / "TEMP-0.in").read_text(encoding="utf-8")
    grdecl = (output_root / "include" / "TEMP_GRD.grdecl").read_text(encoding="utf-8")
    assert "FINAL_DATE  1 JAN 2125" in deck
    assert "DATUM_D  500 m" in deck
    assert "PRESSURE  51.5175 Bar" in deck
    assert "DATUM_D  2400 m" in deck
    assert "PRESSURE  210 Bar" in deck
    assert "WGC_D  2400 m" in deck
    assert "     4    4" in deck
    assert "     105    4" in deck
    assert "     2400    75.145" in deck
    assert deck.count("     2400    75.145") == 2
    assert deck.count("SALTVD\n     4 0.032\n     2400 0.032") == 2
    assert "WELL_DATA INJ_01" not in deck
    assert "external_file ../include/TEMP_LGR.grdecl /" in grdecl


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


def test_xlsx_grid_policy_applies_legacy_units_and_defaults(tmp_path):
    workbook = tmp_path / "legacy_policy.xlsx"
    _write_minimal_workbook(workbook)

    policy = xlsx_grid_policy(workbook)

    assert policy["depth_unit"] == "m"
    assert policy["permeability_unit"] == "mD"
    assert policy["dx"] == 200.0
    assert policy["reservoir_permx"] == 1000.0


@pytest.mark.parametrize(
    ("key", "value"),
    [("depth_unit", "ft"), ("permeability_unit", "D"), ("target_dz_water", 0), ("reservoir_permx", -1)],
)
def test_xlsx_grid_policy_rejects_invalid_values(tmp_path, key, value):
    workbook = tmp_path / "invalid_policy.xlsx"
    _write_minimal_workbook(workbook)
    excel = load_workbook(workbook)
    sheet = excel["GridPolicy"]
    matching_rows = [row for row in range(2, sheet.max_row + 1) if sheet.cell(row, 1).value == key]
    if matching_rows:
        sheet.cell(matching_rows[0], 2).value = value
    else:
        sheet.append([key, value])
    excel.save(workbook)

    with pytest.raises(ValueError, match="invalid GridPolicy"):
        xlsx_grid_policy(workbook)


def test_xlsx_grid_policy_converts_header_elevation_from_feet(tmp_path):
    workbook = tmp_path / "feet_header.xlsx"
    _write_minimal_workbook(workbook)
    excel = load_workbook(workbook)
    sheet = excel["Header"]
    for row in range(2, sheet.max_row + 1):
        if sheet.cell(row, 1).value == "ground_elevation":
            sheet.cell(row, 2).value = 1000.0
        elif sheet.cell(row, 1).value == "ground_elevation_unit":
            sheet.cell(row, 2).value = "ft"
    excel.save(workbook)

    assert xlsx_grid_policy(workbook)["water_depth"] == pytest.approx(304.8)


def test_case_name_defaults_to_default_when_omitted(tmp_path):
    """Verify that --case-name defaults to 'default' when omitted."""
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
    ]
    subprocess.run(command, check=True, cwd=repo_root, capture_output=True, text=True)

    # Should succeed without specifying --case-name
    assert (output_root / "model" / "TEMP-0.in").exists()


def test_case_name_selection_with_multi_scenario(tmp_path):
    """Verify that --case-name selects the correct scenario from multi-scenario workbook."""
    workbook = tmp_path / "multi_scenario.xlsx"
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

    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        metadata.to_excel(writer, sheet_name="Metadata", index=False)
        header.to_excel(writer, sheet_name="Header", index=False)
        grid_policy.to_excel(writer, sheet_name="GridPolicy", index=False)
        pd.DataFrame(
            {
                "case_name": ["default", "hot_case"],
                "temperature_gradient": [31.0, 40.0],
                "ground_temperature": [4.0, 5.0],
                "z_fluid_contact": [2400.0, 2350.0],
                "p_fluid_contact": [210.0, 220.0],
                "overburden_datum_depth": [500.0, 500.0],
                "z_resrv": [1400.0, 1400.0],
                "p_resrv": [250.0, 260.0],
            }
        ).to_excel(writer, sheet_name="SubsurfaceAssumptions", index=False)

    design = xlsx_to_simulation_design(workbook)
    default_scenario = design.select("default")
    hot_scenario = design.select("hot_case")

    assert default_scenario.temperature_gradient == 31.0
    assert hot_scenario.temperature_gradient == 40.0


def test_case_name_raises_error_for_unknown_case(tmp_path):
    """Verify that selecting an unknown case name raises an error."""
    workbook = tmp_path / "well_input.xlsx"
    _write_minimal_workbook(workbook)

    design = xlsx_to_simulation_design(workbook)
    try:
        design.select("nonexistent_case")
    except ValueError as exc:
        assert "unknown simulation case" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown case name")

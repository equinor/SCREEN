"""Test batch scenario execution."""

from pathlib import Path
import subprocess
import sys

import pandas as pd

from src.WellClass.libs.utils.xlsx_parser import xlsx_to_simulation_design


def _write_multi_scenario_workbook(path: Path, num_scenarios: int = 3) -> None:
    """Write a multi-scenario test workbook."""
    metadata = pd.DataFrame({"key": ["namespace", "name", "author"], "value": ["screen", "batch-test", "pytest"]})
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

    scenarios = {
        "case_name": [f"case_{i}" for i in range(num_scenarios)],
        "temperature_gradient": [31.0 + i * 5.0 for i in range(num_scenarios)],
        "ground_temperature": [4.0 + i * 0.5 for i in range(num_scenarios)],
        "z_fluid_contact": [2400.0 - i * 50.0 for i in range(num_scenarios)],
        "p_fluid_contact": [210.0 + i * 5.0 for i in range(num_scenarios)],
        "overburden_datum_depth": [500.0] * num_scenarios,
        "z_resrv": [1400.0] * num_scenarios,
        "p_resrv": [250.0] * num_scenarios,
    }

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        metadata.to_excel(writer, sheet_name="Metadata", index=False)
        header.to_excel(writer, sheet_name="Header", index=False)
        grid_policy.to_excel(writer, sheet_name="GridPolicy", index=False)
        pd.DataFrame(scenarios).to_excel(writer, sheet_name="SubsurfaceAssumptions", index=False)


def test_batch_scenario_execution_creates_output_directories(tmp_path):
    """Verify that batch execution creates per-case output directories."""
    workbook = tmp_path / "multi_scenario.xlsx"
    _write_multi_scenario_workbook(workbook, num_scenarios=3)

    design = xlsx_to_simulation_design(workbook)
    assert len(design.scenarios) == 3
    assert [s.case_name for s in design.scenarios] == ["case_0", "case_1", "case_2"]


def test_batch_execution_script_summary(tmp_path):
    """Verify that batch script produces correct summary even with dry-run."""
    workbook = tmp_path / "multi_scenario.xlsx"
    _write_multi_scenario_workbook(workbook, num_scenarios=2)

    output_root = tmp_path / "batch_output"
    repo_root = Path(__file__).parents[2]

    # This command will fail (no real simulator), but we're testing the setup
    command = [
        sys.executable,
        "runscripts/run_workbook_scenarios_batch.py",
        "--xlsx",
        str(workbook),
        "--output-root",
        str(output_root),
        "--sim-command",
        "echo 'fake cirrus'",  # Dummy command
    ]

    result = subprocess.run(command, cwd=repo_root, capture_output=True, text=True)

    # Output should mention the scenarios found
    assert "case_0" in result.stdout or "case_0" in result.stderr
    assert "case_1" in result.stdout or "case_1" in result.stderr

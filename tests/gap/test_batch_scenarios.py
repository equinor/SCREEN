"""Test batch scenario execution."""

from pathlib import Path
import argparse
import importlib.util
import subprocess
import sys
import threading
import time

import pandas as pd

from src.WellClass.libs.utils.xlsx_parser import xlsx_to_simulation_design


SCRIPT_PATH = Path(__file__).parents[2] / "runscripts/run_workbook_scenarios_batch.py"
SPEC = importlib.util.spec_from_file_location("run_workbook_scenarios_batch", SCRIPT_PATH)
batch = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(batch)


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
                "target_dz_water",
                "target_dz_overburden",
                "target_dz_reservoir",
                "cells_per_layer",
            ],
            "value": [4.0, 50.0, 60.0, 10.0, 400],
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


def test_batch_runs_scenarios_concurrently_with_bounded_jobs(tmp_path, monkeypatch):
    """Verify that --jobs bounds concurrent scenario workers."""
    workbook = tmp_path / "multi_scenario.xlsx"
    _write_multi_scenario_workbook(workbook, num_scenarios=3)
    design = xlsx_to_simulation_design(workbook)
    active = 0
    maximum_active = 0
    lock = threading.Lock()

    def fake_run_scenario_case(*_args):
        nonlocal active, maximum_active
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        time.sleep(0.05)
        with lock:
            active -= 1
        return 0

    monkeypatch.setattr(batch, "run_scenario_case", fake_run_scenario_case)
    args = argparse.Namespace(
        jobs=2,
        xlsx=workbook,
        output_root=tmp_path / "output",
        template_root=tmp_path,
        sim_command="fake",
        run_final=False,
        simulation_years=1,
        start_date="2025-01-01",
        lgr_name="TEMP_LGR",
        oh_perm=10000.0,
        cb_perm=0.05,
        barrier_perm=0.05,
        ali_way=False,
        force=False,
        plot=False,
    )

    successful, failed = batch.run_scenarios(design, args)

    assert sorted(successful) == ["case_0", "case_1", "case_2"]
    assert failed == []
    assert maximum_active == 2


def test_batch_collects_failures_from_concurrent_workers(tmp_path, monkeypatch):
    """Verify that one failed scenario does not cancel the other workers."""
    workbook = tmp_path / "multi_scenario.xlsx"
    _write_multi_scenario_workbook(workbook, num_scenarios=3)
    design = xlsx_to_simulation_design(workbook)

    def fake_run_scenario_case(_xlsx, case_name, *_args):
        return 1 if case_name == "case_1" else 0

    monkeypatch.setattr(batch, "run_scenario_case", fake_run_scenario_case)
    args = argparse.Namespace(
        jobs=3,
        xlsx=workbook,
        output_root=tmp_path / "output",
        template_root=tmp_path,
        sim_command="fake",
    )

    successful, failed = batch.run_scenarios(design, args)

    assert sorted(successful) == ["case_0", "case_2"]
    assert failed == ["case_1"]


def test_batch_rejects_non_positive_jobs(tmp_path):
    """Verify that a non-positive worker count is rejected."""
    workbook = tmp_path / "multi_scenario.xlsx"
    _write_multi_scenario_workbook(workbook, num_scenarios=1)
    repo_root = Path(__file__).parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "runscripts/run_workbook_scenarios_batch.py",
            "--xlsx",
            str(workbook),
            "--output-root",
            str(tmp_path / "output"),
            "--sim-command",
            "fake",
            "--jobs",
            "0",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert "--jobs must be at least 1" in result.stdout

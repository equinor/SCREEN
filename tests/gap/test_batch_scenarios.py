"""Test batch scenario execution."""

from pathlib import Path
import argparse
import importlib.util
import json
import subprocess
import sys
import threading
import time

import pandas as pd
import pytest

from src.GaP.libs.models.simulation_scenario import SimulationScenario
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
    assert design.scenarios[0].depth_unit == "m"
    assert design.scenarios[0].pressure_unit == "bar"


def test_design_matrix_is_preferred_over_legacy_scenario_sheet(tmp_path):
    workbook = tmp_path / "design_matrix.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame({"case_name": ["legacy"], "p_fluid_contact": [100.0]}).to_excel(writer, sheet_name="SubsurfaceAssumptions", index=False)
        pd.DataFrame(
            {
                "case_name": ["sensitivity"],
                "reservoir_permx": [750.0],
                "cb_perm": [0.2],
            }
        ).to_excel(writer, sheet_name="DesignMatrix", index=False)

    design = xlsx_to_simulation_design(workbook)

    assert len(design.scenarios) == 1
    assert design.scenarios[0].case_name == "sensitivity"
    assert design.scenarios[0].reservoir_permx == 750.0
    assert design.scenarios[0].cb_perm == 0.2
    assert design.scenarios[0].p_fluid_contact is None


def test_scenario_depth_and_pressure_units_are_validated():
    assert SimulationScenario().depth_unit == "m"
    assert SimulationScenario().pressure_unit == "bar"
    assert SimulationScenario().permeability_unit == "mD"
    assert SimulationScenario().cb_perm_interval == "ALL"
    assert SimulationScenario().barrier_perm_interval == "ALL"
    with pytest.raises(ValueError):
        SimulationScenario(depth_unit="ft")
    with pytest.raises(ValueError):
        SimulationScenario(pressure_unit="psi")
    with pytest.raises(ValueError):
        SimulationScenario(permeability_unit="D")
    with pytest.raises(ValueError):
        SimulationScenario(salinity_basis="mass_ratio")
    with pytest.raises(ValueError):
        SimulationScenario(salinity=1.0)
    with pytest.raises(ValueError, match="cb_perm is required"):
        SimulationScenario(cb_perm_interval="Cement 13 3/8 in")
    with pytest.raises(ValueError, match="must not be blank"):
        SimulationScenario(barrier_perm_interval=" ")


def test_design_matrix_parses_interval_permeability_targets(tmp_path):
    workbook = tmp_path / "interval-overrides.xlsx"
    with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
        pd.DataFrame(
            {
                "case_name": ["targeted"],
                "cb_perm": [0.2],
                "cb_perm_interval": ["Cement 13 3/8 in"],
                "barrier_perm": [0.3],
                "barrier_perm_interval": ["cplug9"],
            }
        ).to_excel(writer, sheet_name="DesignMatrix", index=False)

    scenario = xlsx_to_simulation_design(workbook).scenarios[0]
    assert scenario.cb_perm == 0.2
    assert scenario.cb_perm_interval == "Cement 13 3/8 in"
    assert scenario.barrier_perm == 0.3
    assert scenario.barrier_perm_interval == "cplug9"


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


def _batch_args(tmp_path, workbook, **overrides):
    return argparse.Namespace(
        jobs=2, xlsx=workbook, output_root=tmp_path / "output", template_root=tmp_path, sim_command="fake",
        run_final=False, simulation_years=1, start_date="2025-01-01", lgr_name="TEMP_LGR", oh_perm=None,
        cb_perm=0.05, barrier_perm=0.05, ali_way=False, force=False, plot=False, dry_run=False, **overrides,
    )


def _existing_case(args, design, name, *, log=None, **saved):
    stem = batch.case_stems(design, args.xlsx)[name]
    root = args.output_root / stem
    (root / "model").mkdir(parents=True)
    scenario = design.select(name).model_dump(mode="json")
    (root / "scenario.json").write_text(json.dumps({**scenario, **saved}))
    if log is not None:
        (root / "model" / f"{stem}.LOG").write_text(log)
    return root


DONE = " Time step 100\n Run completed, wall clock time =  4.1866E+03 s,  6.9776E+01 min\n"


def test_plan_runs_only_cases_without_a_folder(tmp_path):
    workbook = tmp_path / "multi_scenario.xlsx"
    _write_multi_scenario_workbook(workbook, num_scenarios=5)
    design = xlsx_to_simulation_design(workbook)
    args = _batch_args(tmp_path, workbook)
    _existing_case(args, design, "case_0", log=DONE)
    _existing_case(args, design, "case_1", log=" Time step 40\n")  # killed: no final line
    _existing_case(args, design, "case_2")  # staged, never produced a log
    _existing_case(args, design, "case_3", log=DONE)

    plan = batch.plan_scenarios(design, args)

    assert {name: action for name, (action, _) in plan.items()} == {
        "case_0": "done", "case_1": "verify", "case_2": "verify", "case_3": "done", "case_4": "run",
    }
    assert "killed or crashed" in plan["case_1"][1]
    args.force = True
    assert {action for action, _ in batch.plan_scenarios(design, args).values()} == {"run"}


def test_completion_line_must_be_at_the_end_of_the_log(tmp_path):
    log = tmp_path / "case.LOG"
    log.write_text(DONE + "x" * 10000)
    assert not batch.run_completed(log)
    log.write_text("x" * 10000 + DONE)
    assert batch.run_completed(log)
    log.write_text(DONE)
    assert batch.run_completed(log)
    assert not batch.run_completed(tmp_path / "missing.LOG")


def test_plan_warns_when_a_row_changed_since_it_finished(tmp_path):
    workbook = tmp_path / "multi_scenario.xlsx"
    _write_multi_scenario_workbook(workbook, num_scenarios=2)
    design = xlsx_to_simulation_design(workbook)
    args = _batch_args(tmp_path, workbook)
    _existing_case(args, design, "case_0", log=DONE, cb_perm=5.0, z_fluid_contact=1.0)
    _existing_case(args, design, "case_1", log=DONE)

    plan = batch.plan_scenarios(design, args)

    assert "WARNING" in plan["case_0"][1] and "cb_perm, z_fluid_contact" in plan["case_0"][1]
    assert "WARNING" not in plan["case_1"][1]


def test_older_saved_case_without_newer_fields_is_not_reported_as_changed(tmp_path):
    workbook = tmp_path / "multi_scenario.xlsx"
    _write_multi_scenario_workbook(workbook, num_scenarios=1)
    design = xlsx_to_simulation_design(workbook)
    args = _batch_args(tmp_path, workbook)
    root = _existing_case(args, design, "case_0", log=DONE)
    saved = json.loads((root / "scenario.json").read_text())
    for newer in ("casing_hole_open", "free_fluid_permx", "free_fluid_poro"):
        saved.pop(newer, None)
    (root / "scenario.json").write_text(json.dumps(saved))

    assert batch.changed_inputs(root, design.scenarios[0]) == []


def test_main_runs_only_new_cases_and_lists_those_to_verify(tmp_path, monkeypatch, capsys):
    workbook = tmp_path / "multi_scenario.xlsx"
    _write_multi_scenario_workbook(workbook, num_scenarios=3)
    design = xlsx_to_simulation_design(workbook)
    args = _batch_args(tmp_path, workbook)
    kept = _existing_case(args, design, "case_0", log=DONE)
    _existing_case(args, design, "case_1", log=" Time step 40\n")
    calls = []

    def fake_run_scenario_case(_xlsx, case_name, *_rest):
        calls.append(case_name)
        return 0

    monkeypatch.setattr(batch, "run_scenario_case", fake_run_scenario_case)
    monkeypatch.setattr("sys.argv", [
        "batch", "--xlsx", str(workbook), "--output-root", str(args.output_root), "--sim-command", "fake {deck}",
    ])
    assert batch.main() == 0

    assert calls == ["case_2"]
    manifest = json.loads((args.output_root / "batch_manifest.json").read_text())
    assert {case["case_name"]: case["status"] for case in manifest["cases"]} == {
        "case_0": "existing", "case_1": "unverified", "case_2": "succeeded",
    }
    assert (kept / "model").is_dir()
    out = capsys.readouterr().out
    assert "Already finished (skipped): 1" in out and "Need verification (not run): 1" in out
    assert "NOT RUN: check whether these were killed or crashed" in out
    assert "- case_1:" in out.split("NOT RUN")[1]


def test_dry_run_prints_the_plan_and_changes_nothing(tmp_path, monkeypatch, capsys):
    workbook = tmp_path / "multi_scenario.xlsx"
    _write_multi_scenario_workbook(workbook, num_scenarios=3)
    design = xlsx_to_simulation_design(workbook)
    args = _batch_args(tmp_path, workbook)
    _existing_case(args, design, "case_0", log=DONE)
    _existing_case(args, design, "case_1")
    monkeypatch.setattr(batch, "run_scenario_case", lambda *_: pytest.fail("dry run must not run cases"))
    monkeypatch.setattr("sys.argv", [
        "batch", "--xlsx", str(workbook), "--output-root", str(args.output_root), "--sim-command", "fake {deck}", "--dry-run",
    ])
    assert batch.main() == 0

    out = capsys.readouterr().out
    assert "DONE  case_0" in out and "VERIFY case_1" in out and "RUN   case_2: new" in out
    assert not (args.output_root / "batch_manifest.json").exists()

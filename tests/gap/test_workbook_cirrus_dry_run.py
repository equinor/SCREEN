from pathlib import Path
import json
import importlib.util
import subprocess
import sys
import types
from types import SimpleNamespace

import numpy as np

WORKFLOW_PATH = Path(__file__).parents[2] / "runscripts/run_workbook_to_cirrus_lgr.py"
sys.path.insert(0, str(WORKFLOW_PATH.parent))
WORKFLOW_SPEC = importlib.util.spec_from_file_location("run_workbook_to_cirrus_lgr", WORKFLOW_PATH)
workflow = importlib.util.module_from_spec(WORKFLOW_SPEC)
assert WORKFLOW_SPEC.loader is not None
WORKFLOW_SPEC.loader.exec_module(workflow)


def _fake_cirrus(tmp_path: Path, fixture_prefix: Path) -> Path:
    runner = tmp_path / "fake-cirrus"
    runner.write_text(
        "#!/bin/sh\n"
        f'cp "{fixture_prefix}.EGRID" "${{1%.in}}.EGRID"\n'
        f'cp "{fixture_prefix}.INIT" "${{1%.in}}.INIT"\n'
        'echo "fake CIRRUS completed"\n',
        encoding="utf-8",
    )
    runner.chmod(0o755)
    return runner


def test_workbook_wrapper_runs_full_dry_run_without_cirrus(tmp_path):
    root = Path(__file__).parents[2]
    output_root = tmp_path / "case"
    fixture_prefix = root / "test_data/examples/wildcat/model/TEMP-0"
    runner = _fake_cirrus(tmp_path, fixture_prefix)

    subprocess.run(
        [
            sys.executable,
            "runscripts/run_workbook_to_cirrus_lgr.py",
            "--xlsx",
            "test_data/examples/wildcat/wildcat_workbook.xlsx",
            "--output-root",
            str(output_root),
            "--sim-command",
            f"{runner} {{deck}}",
            "--run-final",
            "--simulation-years",
            "0",
            "--case-name",
            "baseline",
            "--plot",
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    assert (output_root / "well_input.json").exists()
    scenario = json.loads((output_root / "scenario.json").read_text(encoding="utf-8"))
    assert scenario["case_name"] == "baseline"
    assert scenario["temperature_gradient"] == 31.0
    assert (output_root / "qc_plot.png").stat().st_size > 0
    assert (output_root / "model/TEMP-0.EGRID").exists()
    assert (output_root / "model/TEMP-0.INIT").exists()
    assert (output_root / "include/TEMP_LGR.grdecl").exists()
    assert (output_root / "logs/initialization.log").read_text(encoding="utf-8") == "fake CIRRUS completed\n"
    assert (output_root / "logs/final.log").read_text(encoding="utf-8") == "fake CIRRUS completed\n"
    assert "FINAL_DATE  1 JAN 2025" in (output_root / "model/TEMP-0.in").read_text(encoding="utf-8")


def test_qc_plot_uses_workbook_fluid_contact_pressure(tmp_path, monkeypatch):
    """Verify that the WellClass QC curve uses the scenario pressure datum."""
    captured = {}

    class FakePressureScenario:
        def display_curves(self):
            return {
                "brine_pressure": np.array([100.0, 110.0]),
                "brine_depth": np.array([0.0, 10.0]),
                "fluid_pressure": np.array([200.0, 210.0]),
                "fluid_depth": np.array([0.0, 10.0]),
            }

    class FakePressure:
        def __init__(self, **kwargs):
            self.table = SimpleNamespace(
                depth=np.array([0.0, 10.0]),
                hydrostatic_pressure=np.array([100.0, 105.0]),
                min_horizontal_stress=np.array([90.0, 95.0]),
            )

        def add_scenario(self, name, **kwargs):
            captured.update(name=name, **kwargs)
            return FakePressureScenario()

    monkeypatch.setattr(workflow, "Pressure", FakePressure)
    monkeypatch.setattr(workflow, "WellProcessed", SimpleNamespace(from_pydantic=lambda model: SimpleNamespace(header={})))
    plotting_module = types.ModuleType("src.WellClass.libs.plotting.plot_sketch")
    plotting_module.plot_sketch = lambda *_args, **_kwargs: None
    monkeypatch.setitem(sys.modules, "src.WellClass.libs.plotting.plot_sketch", plotting_module)

    scenario = SimpleNamespace(
        case_name="pressure_case",
        z_fluid_contact=2400.0,
        p_fluid_contact=245.0,
        z_resrv=1400.0,
        p_resrv=250.0,
        ground_temperature=4.0,
        temperature_gradient=31.0,
        fluid_type="co2",
    )

    workflow.save_qc_plot(SimpleNamespace(), scenario, tmp_path / "qc_plot.png")

    assert captured["z_fluid_datum"] == 2400.0
    assert captured["p_fluid_datum"] == 245.0

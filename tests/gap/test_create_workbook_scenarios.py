"""Test workbook generation with multi-scenario support."""

from pathlib import Path
import subprocess
import sys

from src.WellClass.libs.utils.xlsx_parser import xlsx_to_simulation_design


def test_create_workbook_with_single_scenario(tmp_path):
    """Verify workbook generation with single scenario."""
    output = tmp_path / "single_scenario.xlsx"
    repo_root = Path(__file__).parents[2]

    command = [
        sys.executable,
        "runscripts/create_well_input_workbook.py",
        "--output",
        str(output),
    ]
    result = subprocess.run(command, cwd=repo_root, capture_output=True, text=True)

    assert result.returncode == 0
    assert output.exists()
    assert "default" in result.stdout

    design = xlsx_to_simulation_design(output)
    assert len(design.scenarios) == 1
    assert design.scenarios[0].case_name == "default"


def test_create_workbook_with_multi_scenarios(tmp_path):
    """Verify workbook generation with multiple scenarios."""
    output = tmp_path / "multi_scenario.xlsx"
    repo_root = Path(__file__).parents[2]

    command = [
        sys.executable,
        "runscripts/create_well_input_workbook.py",
        "--output",
        str(output),
        "--scenarios",
        "baseline",
        "hot_case",
        "conservative",
    ]
    result = subprocess.run(command, cwd=repo_root, capture_output=True, text=True)

    assert result.returncode == 0
    assert output.exists()
    assert "baseline" in result.stdout
    assert "hot_case" in result.stdout
    assert "conservative" in result.stdout

    design = xlsx_to_simulation_design(output)
    assert len(design.scenarios) == 3
    case_names = [s.case_name for s in design.scenarios]
    assert case_names == ["baseline", "hot_case", "conservative"]

    # Verify temperature gradient progression (each scenario hotter)
    baseline = design.scenarios[0]
    hot = design.scenarios[1]
    conservative = design.scenarios[2]
    assert hot.temperature_gradient > baseline.temperature_gradient
    assert conservative.temperature_gradient > hot.temperature_gradient


def test_workbook_scenario_variations_have_distinct_values(tmp_path):
    """Verify that generated scenarios have progressively varying values."""
    output = tmp_path / "variations.xlsx"
    repo_root = Path(__file__).parents[2]

    command = [
        sys.executable,
        "runscripts/create_well_input_workbook.py",
        "--output",
        str(output),
        "--scenarios",
        "case_0",
        "case_1",
        "case_2",
    ]
    subprocess.run(command, cwd=repo_root, check=True, capture_output=True)

    design = xlsx_to_simulation_design(output)
    s0 = design.scenarios[0]
    s1 = design.scenarios[1]
    s2 = design.scenarios[2]

    # Check progressively increasing temperature gradients
    assert s0.temperature_gradient == 31.0
    assert s1.temperature_gradient == 36.0
    assert s2.temperature_gradient == 41.0

    # Check progressively increasing ground temperature
    assert s0.ground_temperature == 4.0
    assert s1.ground_temperature == 5.0
    assert s2.ground_temperature == 6.0

    # Check progressively decreasing fluid contact depth (shallower)
    assert s0.z_fluid_contact == 2400.0
    assert s1.z_fluid_contact == 2375.0
    assert s2.z_fluid_contact == 2350.0

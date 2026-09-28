import importlib.util
import json
from pathlib import Path

import numpy as np


SCRIPT_PATH = Path(__file__).parents[2] / "runscripts/compare_scenario_outputs.py"
SPEC = importlib.util.spec_from_file_location("compare_scenario_outputs", SCRIPT_PATH)
compare = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(compare)


class FakeCase:
    def __init__(self, prefix):
        self.name = prefix.parent.parent.name
        self.value = 0.0 if self.name == "alpha" else 1.0
        self.restart_keywords = ["PRESSURE", "SWAT", "SGAS"]
        self.restart_timesteps = [{"days": 0.0}]
        self.keywords = ["PERMX", "PORO", "EQLNUM"]

    @property
    def dimensions(self):
        return (1, 1, 2, 2) if self.name == "geometry_variant" else (1, 1, 1, 1)

    def cell_corners(self):
        count = self.dimensions[3]
        return np.zeros((count, 24))

    def init_vector(self, keyword):
        if keyword == "PERMX" and self.name == "zulu":
            return np.array([200.0])
        return np.array([100.0 if keyword == "PERMX" else 1.0])

    def restart_lgr_vector(self, _keyword, _timestep):
        return np.array([self.value])


def _write_case(root: Path, name: str) -> None:
    case_root = root / name
    lgr_path = case_root / compare.LGR_FILE
    lgr_path.parent.mkdir(parents=True, exist_ok=True)
    lgr_path.write_text("CARFIN\nTEMP_LGR 10 10 10 10 1 63 22 22 270 /\nPERMX 100 5 18 5 18 71 82 /\n", encoding="utf-8")
    (case_root / "scenario.json").write_text(
        '{"case_name": "' + name + '", "p_fluid_contact": 100}\n', encoding="utf-8"
    )
    grid_policy = {"nx": 21 if name == "geometry_variant" else 20, "reservoir_permx": 200 if name == "zulu" else 100}
    (case_root / "grid_policy.json").write_text(
        json.dumps(grid_policy) + "\n", encoding="utf-8"
    )
    model_root = case_root / "model"
    model_root.mkdir(parents=True, exist_ok=True)
    (model_root / "TEMP-0.UNRST").write_text("restart", encoding="utf-8")


def test_compare_outputs_uses_named_baseline(monkeypatch, tmp_path):
    _write_case(tmp_path, "alpha")
    _write_case(tmp_path, "zulu")
    monkeypatch.setattr(compare, "ResdataCase", FakeCase)

    report = compare.compare_outputs(tmp_path, "zulu")

    assert report["valid"] is True
    assert report["baseline"] == "zulu"
    comparison = report["comparisons"][0]
    assert comparison["case_name"] == "alpha"
    assert comparison["geometry_invariants_hold"] is True
    assert comparison["changed_scenario_fields"] == []
    assert comparison["grid_policy_comparison_available"] is True
    assert comparison["changed_grid_policy_fields"] == ["reservoir_permx"]
    assert comparison["init_properties"]["PERMX"]["equal"] is False
    assert comparison["dynamic_outputs_differ"] is True


def test_compare_outputs_flags_geometry_policy_changes(monkeypatch, tmp_path):
    _write_case(tmp_path, "alpha")
    _write_case(tmp_path, "geometry_variant")
    monkeypatch.setattr(compare, "ResdataCase", FakeCase)

    report = compare.compare_outputs(tmp_path, "alpha")

    comparison = report["comparisons"][0]
    assert report["valid"] is False
    assert comparison["geometry_invariants_hold"] is False
    assert comparison["geometry_policy_fields_changed"] == ["nx"]
    assert any("grid sensitivity study" in error for error in comparison["validation_errors"])


def test_lgr_geometry_signature_ignores_property_value_changes(tmp_path):
    baseline = tmp_path / "baseline.grdecl"
    sensitivity = tmp_path / "sensitivity.grdecl"
    baseline.write_text("CARFIN\nTEMP_LGR 10 10 10 10 1 63 22 22 270 /\nPERMX 100 5 18 5 18 71 82 /\n", encoding="utf-8")
    sensitivity.write_text("CARFIN\nTEMP_LGR 10 10 10 10 1 63 22 22 270 /\nPERMX 500 5 18 5 18 71 82 /\n", encoding="utf-8")

    assert compare.lgr_geometry_signature(baseline) == compare.lgr_geometry_signature(sensitivity)

    sensitivity.write_text("CARFIN\nTEMP_LGR 10 10 10 10 1 63 22 22 270 /\nPERMX 500 5 19 5 18 71 82 /\n", encoding="utf-8")
    assert compare.lgr_geometry_signature(baseline) != compare.lgr_geometry_signature(sensitivity)


def test_compare_outputs_rejects_unknown_baseline(tmp_path):
    _write_case(tmp_path, "alpha")

    report = compare.compare_outputs(tmp_path, "missing")

    assert report == {"valid": False, "error": "baseline scenario not found: missing"}
import importlib.util
from pathlib import Path

import numpy as np


SCRIPT_PATH = Path(__file__).parents[2] / "runscripts/compare_scenario_outputs.py"
SPEC = importlib.util.spec_from_file_location("compare_scenario_outputs", SCRIPT_PATH)
compare = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(compare)


class FakeCase:
    def __init__(self, prefix):
        self.value = 0.0 if prefix.parent.parent.name == "alpha" else 1.0
        self.restart_keywords = ["PRESSURE"]
        self.restart_timesteps = [{"days": 0.0}]

    def restart_lgr_vector(self, _keyword, _timestep):
        return np.array([self.value])


def _write_case(root: Path, name: str) -> None:
    case_root = root / name
    for relative_path in compare.STATIC_FILES:
        path = case_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("same", encoding="utf-8")
    (case_root / "scenario.json").write_text(
        '{"case_name": "' + name + '"}\n', encoding="utf-8"
    )
    (case_root / "model" / "TEMP-0.UNRST").write_text("restart", encoding="utf-8")


def test_compare_outputs_uses_named_baseline(monkeypatch, tmp_path):
    _write_case(tmp_path, "alpha")
    _write_case(tmp_path, "zulu")
    monkeypatch.setattr(compare, "ResdataCase", FakeCase)

    report = compare.compare_outputs(tmp_path, "zulu")

    assert report["valid"] is True
    assert report["baseline"] == "zulu"
    assert report["comparisons"][0]["case_name"] == "alpha"


def test_compare_outputs_rejects_unknown_baseline(tmp_path):
    _write_case(tmp_path, "alpha")

    report = compare.compare_outputs(tmp_path, "missing")

    assert report == {"valid": False, "error": "baseline scenario not found: missing"}
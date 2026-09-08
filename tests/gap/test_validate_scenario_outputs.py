from pathlib import Path
import json
import subprocess
import sys

REQUIRED_OUTPUTS = (
    "include/TEMP_GRD.grdecl",
    "include/TEMP_LGR.grdecl",
    "model/TEMP-0.EGRID",
    "model/TEMP-0.INIT",
)


def _write_case(root: Path, *, log_text: str = "CIRRUS completed\n") -> None:
    for relative_path in REQUIRED_OUTPUTS:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative_path, encoding="utf-8")
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "initialization.log").write_text(log_text, encoding="utf-8")


def test_validate_outputs_accepts_complete_cases(tmp_path):
    _write_case(tmp_path / "baseline")

    report_path = tmp_path / "report.json"
    result = subprocess.run(
        [
            sys.executable,
            "runscripts/validate_scenario_outputs.py",
            "--output-root",
            str(tmp_path),
            "--report",
            str(report_path),
        ],
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
        check=True,
    )
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["valid"] is True
    assert report["cases"][0]["case_name"] == "baseline"
    assert len(report["cases"][0]["files"]) == 4
    assert "OK: baseline" in result.stdout


def test_validate_outputs_reports_missing_files(tmp_path):
    case_root = tmp_path / "baseline"
    _write_case(case_root)
    (case_root / "model/TEMP-0.INIT").unlink()

    result = subprocess.run(
        [sys.executable, "runscripts/validate_scenario_outputs.py", "--output-root", str(tmp_path)],
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "missing or empty file: model/TEMP-0.INIT" in result.stdout


def test_validate_outputs_reports_log_errors(tmp_path):
    _write_case(tmp_path / "baseline", log_text="FATAL: simulator failed\n")

    result = subprocess.run(
        [sys.executable, "runscripts/validate_scenario_outputs.py", "--output-root", str(tmp_path)],
        cwd=Path(__file__).parents[2],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "log error:" in result.stdout
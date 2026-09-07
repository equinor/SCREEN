from pathlib import Path
import subprocess
import sys


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
        ],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )

    assert (output_root / "well_input.json").exists()
    assert (output_root / "model/TEMP-0.EGRID").exists()
    assert (output_root / "model/TEMP-0.INIT").exists()
    assert (output_root / "include/TEMP_LGR.grdecl").exists()
    assert (output_root / "logs/initialization.log").read_text(encoding="utf-8") == "fake CIRRUS completed\n"
    assert (output_root / "logs/final.log").read_text(encoding="utf-8") == "fake CIRRUS completed\n"
    assert "FINAL_DATE  1 JAN 2025" in (output_root / "model/TEMP-0.in").read_text(encoding="utf-8")

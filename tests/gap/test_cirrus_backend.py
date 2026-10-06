import os
from pathlib import Path

import pytest

from src.GaP.libs.cirrus_backend import CirrusBackend


def _deck(tmp_path: Path) -> Path:
    deck = tmp_path / "model" / "TEMP-0.in"
    deck.parent.mkdir()
    deck.write_text("deck", encoding="utf-8")
    return deck


def _runner(tmp_path: Path, body: str) -> Path:
    runner = tmp_path / "fake-cirrus"
    runner.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    runner.chmod(0o755)
    return runner


def _tool(tmp_path: Path, name: str, body: str) -> Path:
    tool = tmp_path / name
    tool.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    tool.chmod(0o755)
    return tool


def test_backend_reports_unavailable_executable(tmp_path):
    backend = CirrusBackend("not-a-cirrus-command -i {deck}")

    assert not backend.available
    with pytest.raises(FileNotFoundError, match="not available"):
        backend.run(_deck(tmp_path), phase="initialization")


def test_backend_captures_log_and_grid_outputs(tmp_path):
    deck = _deck(tmp_path)
    runner = _runner(tmp_path, 'touch "${1%.in}.EGRID" "${1%.in}.INIT"; echo "simulator output"')
    backend = CirrusBackend(f"{runner} {{deck}}")

    result = backend.run(deck, phase="initialization", require_grid_outputs=True)

    assert result.succeeded
    assert result.egrid_path == deck.with_suffix(".EGRID")
    assert result.init_path == deck.with_suffix(".INIT")
    assert result.log_path.read_text(encoding="utf-8") == "simulator output\n"


def test_backend_requires_grid_outputs_when_requested(tmp_path):
    deck = _deck(tmp_path)
    runner = _runner(tmp_path, 'echo "no grid"')
    backend = CirrusBackend(f"{runner} {{deck}}")

    with pytest.raises(FileNotFoundError, match="did not produce both"):
        backend.run(deck, phase="initialization", require_grid_outputs=True)


def test_backend_waits_for_lsf_outputs_before_checking_them(tmp_path, monkeypatch):
    deck = _deck(tmp_path)
    runner = _runner(tmp_path, 'echo "Job <257620> is submitted to queue <bigmem>."')
    count_file = tmp_path / "bjobs-count"
    lsf = _tool(
        tmp_path,
        "bjobs",
        f'count=$(cat "{count_file}" 2>/dev/null || echo 0)\n'
        f'count=$((count + 1)); echo "$count" > "{count_file}"\n'
        f'if [ "$count" -eq 1 ]; then echo RUN; else touch "{deck.with_suffix(".EGRID")}" "{deck.with_suffix(".INIT")}"; echo DONE; fi',
    )
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")

    backend = CirrusBackend(f"{runner} {{deck}}", queue_poll_interval_seconds=0.001, queue_timeout_seconds=1)
    result = backend.run(deck, phase="initialization", require_grid_outputs=True)

    assert result.succeeded
    assert count_file.read_text(encoding="utf-8").strip() == "2"
    assert result.log_path.read_text(encoding="utf-8").endswith("LSF job 257620 finished with status DONE.\n")


def test_backend_reports_lsf_job_failure(tmp_path, monkeypatch):
    deck = _deck(tmp_path)
    runner = _runner(tmp_path, 'echo "Job <257621> is submitted to queue <bigmem>."')
    _tool(tmp_path, "bjobs", "echo EXIT")
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")

    backend = CirrusBackend(f"{runner} {{deck}}", queue_poll_interval_seconds=0.001, queue_timeout_seconds=1)
    with pytest.raises(RuntimeError, match="LSF job 257621 failed"):
        backend.run(deck, phase="initialization", require_grid_outputs=True)


def test_backend_requires_deck_placeholder():
    with pytest.raises(ValueError, match="{deck}"):
        CirrusBackend("runcirrus -i")

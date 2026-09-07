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


def test_backend_requires_deck_placeholder():
    with pytest.raises(ValueError, match="{deck}"):
        CirrusBackend("runcirrus -i")

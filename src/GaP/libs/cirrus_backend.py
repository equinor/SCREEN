from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CirrusRunResult:
    """Structured result for one CIRRUS command invocation."""

    phase: str
    command: str
    working_directory: Path
    log_path: Path
    return_code: int
    egrid_path: Path | None = None
    init_path: Path | None = None

    @property
    def succeeded(self) -> bool:
        return self.return_code == 0


class CirrusBackend:
    """Run CIRRUS commands with explicit availability checks and log capture."""

    def __init__(self, command_template: str):
        if "{deck}" not in command_template:
            raise ValueError("CIRRUS command template must include a {deck} placeholder")
        self.command_template = command_template

    @property
    def executable(self) -> str:
        return shlex.split(self.command_template)[0]

    @property
    def available(self) -> bool:
        executable = Path(self.executable)
        return executable.is_file() and os.access(executable, os.X_OK) or shutil.which(self.executable) is not None

    def run(self, deck_path: str | Path, *, phase: str, require_grid_outputs: bool = False) -> CirrusRunResult:
        deck_path = Path(deck_path).resolve()
        if not deck_path.exists():
            raise FileNotFoundError(f"CIRRUS deck does not exist: {deck_path}")
        if not self.available:
            raise FileNotFoundError(f"CIRRUS executable is not available: {self.executable}")

        command = self.command_template.format(deck=shlex.quote(str(deck_path)))
        log_path = deck_path.parent.parent / "logs" / f"{phase}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(command, shell=True, cwd=deck_path.parent, capture_output=True, text=True, check=False)
        log_path.write_text(result.stdout + result.stderr, encoding="utf-8")

        prefix = deck_path.with_suffix("")
        egrid_path = prefix.with_suffix(".EGRID")
        init_path = prefix.with_suffix(".INIT")
        run_result = CirrusRunResult(
            phase=phase,
            command=command,
            working_directory=deck_path.parent,
            log_path=log_path,
            return_code=result.returncode,
            egrid_path=egrid_path if egrid_path.exists() else None,
            init_path=init_path if init_path.exists() else None,
        )
        if not run_result.succeeded:
            raise RuntimeError(f"CIRRUS {phase} failed with exit code {result.returncode}; log: {log_path}")
        if require_grid_outputs and (run_result.egrid_path is None or run_result.init_path is None):
            raise FileNotFoundError(f"CIRRUS {phase} completed but did not produce both .EGRID and .INIT; log: {log_path}")
        return run_result

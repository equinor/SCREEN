from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

LSF_SUBMISSION_PATTERN = re.compile(r"Job\s+<(\d+)>\s+is submitted to queue", re.IGNORECASE)


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

    def __init__(self, command_template: str, *, queue_poll_interval_seconds: float = 15.0, queue_timeout_seconds: float = 86400.0):
        if "{deck}" not in command_template:
            raise ValueError("CIRRUS command template must include a {deck} placeholder")
        if queue_poll_interval_seconds <= 0 or queue_timeout_seconds <= 0:
            raise ValueError("queue poll interval and timeout must be positive")
        self.command_template = command_template
        self.queue_poll_interval_seconds = queue_poll_interval_seconds
        self.queue_timeout_seconds = queue_timeout_seconds

    @property
    def executable(self) -> str:
        return shlex.split(self.command_template)[0]

    @property
    def available(self) -> bool:
        executable = Path(self.executable)
        return executable.is_file() and os.access(executable, os.X_OK) or shutil.which(self.executable) is not None

    def _lsf_job_status(self, job_id: str, log_path: Path) -> str:
        if not shutil.which("bjobs"):
            raise RuntimeError(f"LSF job {job_id} was submitted but 'bjobs' is not available; monitor it manually. Log: {log_path}")

        result = subprocess.run(["bjobs", "-a", "-noheader", "-o", "stat", job_id], capture_output=True, text=True, check=False)
        statuses = result.stdout.split()
        if result.returncode == 0 and statuses:
            return statuses[0].upper()

        history = subprocess.run(["bhist", "-l", job_id], capture_output=True, text=True, check=False) if shutil.which("bhist") else None
        history_text = (history.stdout + history.stderr) if history is not None else ""
        match = re.search(r"\bStatus\s+<([A-Z]+)>", history_text, re.IGNORECASE)
        if match:
            return match.group(1).upper()
        if result.returncode != 0 and history is not None and history.returncode != 0:
            raise RuntimeError(
                f"Could not query LSF job {job_id}. bjobs: {result.stderr.strip()}; " f"bhist: {history.stderr.strip()}. Log: {log_path}"
            )
        return "UNKNOWN"

    def _wait_for_lsf_job(self, job_id: str, log_path: Path) -> None:
        started = time.monotonic()
        while True:
            status = self._lsf_job_status(job_id, log_path)
            if status == "DONE":
                with log_path.open("a", encoding="utf-8") as stream:
                    stream.write(f"\nLSF job {job_id} finished with status DONE.\n")
                return
            if status == "EXIT":
                with log_path.open("a", encoding="utf-8") as stream:
                    stream.write(f"\nLSF job {job_id} finished with status EXIT.\n")
                raise RuntimeError(f"CIRRUS LSF job {job_id} failed; inspect {log_path} and the LSF job history")

            elapsed = time.monotonic() - started
            if elapsed >= self.queue_timeout_seconds:
                raise TimeoutError(f"CIRRUS LSF job {job_id} is still {status} after {elapsed:.0f}s; inspect it with bjobs. Log: {log_path}")
            time.sleep(min(self.queue_poll_interval_seconds, self.queue_timeout_seconds - elapsed))

    def run(self, deck_path: str | Path, *, phase: str, require_grid_outputs: bool = False) -> CirrusRunResult:
        deck_path = Path(deck_path).resolve()
        if not deck_path.exists():
            raise FileNotFoundError(f"CIRRUS deck does not exist: {deck_path}")
        if not self.available:
            raise FileNotFoundError(f"CIRRUS executable is not available: {self.executable}")

        command = self.command_template.format(deck=shlex.quote(str(deck_path)))
        log_path = deck_path.parent.parent / "logs" / f"{deck_path.stem}_{phase}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        result = subprocess.run(command, shell=True, cwd=deck_path.parent, capture_output=True, text=True, check=False)
        log_path.write_text(result.stdout + result.stderr, encoding="utf-8")

        if not result.returncode:
            submission = LSF_SUBMISSION_PATTERN.search(result.stdout + result.stderr)
            if submission:
                self._wait_for_lsf_job(submission.group(1), log_path)

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

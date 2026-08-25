from __future__ import annotations

import re
from pathlib import Path


def restrict_co2_equilibration(lgr_path: str | Path, *, first_co2_layer: int) -> Path:
    """Restrict generated LGR EQLNUM 2 ranges to layers below the deepest plug."""

    if first_co2_layer < 1:
        raise ValueError("first_co2_layer must be positive")

    path = Path(lgr_path)
    content = path.read_text(encoding="utf-8")

    def update(match: re.Match[str]) -> str:
        prefix, values, suffix = match.groups()
        fields = values.split()
        k_min = int(fields[-2])
        k_max = int(fields[-1])
        if k_max < first_co2_layer:
            return f"--{prefix}{values}{suffix}"
        fields[-2] = str(max(k_min, first_co2_layer))
        return f"{prefix}{' '.join(fields)}{suffix}"

    pattern = r"(?m)^(\s*EQLNUM\s+2\s+)(.*?)(/\s*)$"
    updated, count = re.subn(pattern, update, content)
    if count == 0:
        raise ValueError("LGR file does not contain an EQLNUM 2 range")
    path.write_text(updated, encoding="utf-8")
    return path

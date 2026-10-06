"""Deterministic, filesystem-safe names for cases generated from a design matrix."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

SCENARIO_FILE = "scenario.json"


@dataclass(frozen=True)
class CaseFiles:
    """Case-root-relative paths of the simulator deck and generated grid includes."""

    deck: Path
    grid: Path
    lgr: Path

    @classmethod
    def for_stem(cls, stem: str) -> CaseFiles:
        return cls(Path("model") / f"{stem}.in", Path("include") / f"{stem}_GRD.grdecl", Path("include") / f"{stem}_LGR.grdecl")

    @classmethod
    def template(cls) -> CaseFiles:
        """Canonical template names, also used by outputs generated before case naming existed."""
        return cls(Path("model/TEMP-0.in"), Path("include/TEMP_GRD.grdecl"), Path("include/TEMP_LGR.grdecl"))

    @property
    def prefix(self) -> Path:
        """Simulator output prefix, without .EGRID/.INIT/.UNRST."""
        return self.deck.with_suffix("")


def sanitize_name(text: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9]+", "_", str(text)).strip("_")
    return sanitized or "case"


def well_label(well_model) -> str:
    """Prefer the workbook Metadata name; fall back to the wellbore identifier."""
    metadata = getattr(well_model, "metadata", None)
    if metadata is not None and getattr(metadata, "name", None):
        return metadata.name
    return well_model.spec.well_header.unique_wellbore_identifier


def resolve_case_stems(well_name: str, case_names: list[str]) -> list[str]:
    """Return one stem per case, appending the 1-based row index only where sanitized names collide."""
    prefix = sanitize_name(well_name)
    stems = [f"{prefix}_{sanitize_name(name)}" for name in case_names]
    # case-insensitive, since some filesystems are
    counts = Counter(stem.lower() for stem in stems)
    stems = [f"{stem}_{index:02d}" if counts[stem.lower()] > 1 else stem for index, stem in enumerate(stems, 1)]
    if len({stem.lower() for stem in stems}) != len(stems):
        raise ValueError(f"could not derive unique case names from: {', '.join(case_names)}")
    return stems


def resolve_case(well_model, design, case_name: str) -> tuple[int, str]:
    """Return the 1-based design-matrix row index and case stem for one case."""
    names = [scenario.case_name for scenario in design.scenarios]
    index = names.index(case_name)
    return index + 1, resolve_case_stems(well_label(well_model), names)[index]


def case_label(case_stem: str, case_name: str, case_index: int, template_root: Path) -> str:
    """One-line description written into the generated deck."""
    return f"{case_stem} | scenario {case_name!r} (DesignMatrix row {case_index}) | template {template_root}"


def case_files(case_root: Path) -> CaseFiles:
    """Resolve a generated case's files from its scenario.json, falling back to template names."""
    path = Path(case_root) / SCENARIO_FILE
    if path.is_file():
        stem = json.loads(path.read_text(encoding="utf-8")).get("case_metadata", {}).get("case_stem")
        if stem:
            return CaseFiles.for_stem(stem)
    return CaseFiles.template()

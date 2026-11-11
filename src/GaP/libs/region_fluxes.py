"""Shared case loading, validation, and units for region-flux plots."""

from __future__ import annotations

import json
import logging
import re
import warnings
from contextlib import closing
from pathlib import Path
from typing import NamedTuple

import numpy as np
from resdata.resfile import ResdataFile
from resdata.summary import Summary

LOGGER = logging.getLogger(__name__)
DAYS_PER_YEAR = 365.25


class Case(NamedTuple):
    name: str
    summary: Summary
    regions: set[int]
    keys: set[str]
    unit: str
    scale: float = 1.0
    inputs: dict | None = None


def surface_density(deck: Path, phase: str) -> float:
    phase = phase.upper()
    if phase not in {"GAS", "WATER"}:
        raise ValueError(f"unsupported EOS phase {phase!r}")
    in_phase = False
    densities = []
    for line in deck.read_text(encoding="utf-8").splitlines():
        tokens = re.split(r"[!#]", line, maxsplit=1)[0].split()
        if not tokens:
            continue
        upper = [token.upper() for token in tokens]
        if upper[0] == "EOS":
            in_phase = upper == ["EOS", phase]
        elif upper[0] == "END":
            in_phase = False
        elif in_phase and upper[0] == "SURFACE_DENSITY":
            if len(tokens) != 3 or upper[2] != "KG/M^3":
                raise ValueError(f"{deck}: EOS {phase} SURFACE_DENSITY must use kg/m^3")
            try:
                density = float(upper[1].replace("D", "E"))
            except ValueError as exc:
                raise ValueError(f"{deck}: invalid EOS {phase} SURFACE_DENSITY value") from exc
            if not np.isfinite(density) or density <= 0:
                raise ValueError(f"{deck}: EOS {phase} SURFACE_DENSITY must be finite and positive")
            densities.append(density)
    if len(densities) != 1:
        raise ValueError(f"{deck}: expected one EOS {phase} SURFACE_DENSITY, found {len(densities)}")
    return densities[0]


def gas_surface_density(deck: Path) -> float:
    return surface_density(deck, "GAS")


def load_inputs(directory: Path) -> dict[str, object]:
    """Load scalar scenario and grid-policy values recorded with a case."""
    inputs: dict[str, object] = {}
    for name in ("scenario.json", "grid_policy.json"):
        path = directory / name
        if path.is_file():
            record = json.loads(path.read_text(encoding="utf-8"))
            inputs.update({key: value for key, value in record.items() if key != "case_name" and not isinstance(value, (dict, list))})
    return inputs


def check_regions(case_name: str, regions: set[int], zonation: str, key: str) -> None:
    for region in map(int, key.split(":")[1].split("-")):
        if region not in regions:
            raise ValueError(f"{case_name}: region {region} does not exist in {zonation}; available regions: {sorted(regions)}")


def has_pair_regions(regions: set[int], key: str) -> bool:
    return all(int(region) in regions for region in key.split(":")[1].split("-"))


def rate_plateau_start(dates: np.ndarray) -> int | None:
    """Select a tail covering at least 30 days and three distinct sample times."""
    cutoff = dates[-1] - np.timedelta64(30, "D")
    if dates[0] > cutoff:
        return None
    start = int(np.searchsorted(dates, cutoff, side="right")) - 1
    while start > 0 and np.unique(dates[start:]).size < 3:
        start -= 1
    if np.unique(dates[start:]).size < 3:
        return None
    return start


def has_rate_plateau(values: np.ndarray, dates: np.ndarray) -> bool:
    """Check a tail of at least 30 days and 3 distinct samples for <=1% range."""
    start = rate_plateau_start(dates)
    if start is None:
        return False
    tail = np.abs(values[start:])
    return bool(np.ptp(tail) <= 0.01 * np.mean(tail))


def annual_mass_rate_scale(values: list[np.ndarray]) -> tuple[float, str]:
    """Scale kg/day values to tonnes, kilotonnes, or megatonnes per year."""
    tonnes_per_year = max(
        (float(np.max(np.abs(value), initial=0.0)) for value in values),
        default=0.0,
    ) * DAYS_PER_YEAR / 1000.0
    if tonnes_per_year >= 1_000_000:
        return DAYS_PER_YEAR / 1_000_000_000.0, "megatonnes/year"
    if tonnes_per_year >= 1_000:
        return DAYS_PER_YEAR / 1_000_000.0, "kilotonnes/year"
    return DAYS_PER_YEAR / 1000.0, "tonnes/year"


def load_cases(
    root: Path, zonation: str, quantity: str, pattern: str, stem: str | None,
    mass: bool = False, reference_case: str | None = None,
) -> list[Case]:
    keyword = f"{quantity}_{zonation[3:]}"
    pair_pattern = re.compile(rf"{keyword}:([1-9][0-9]*)-([1-9][0-9]*)")
    cases = []
    directories = sorted(root.glob(pattern))
    if reference_case is not None:
        if not reference_case or reference_case in (".", "..") or Path(reference_case).name != reference_case:
            raise ValueError("--reference-case must be a case directory name under --output-root, not a path")
        reference = root / reference_case
        if not (reference / "model").is_dir():
            raise ValueError(f"{reference_case}: reference case model directory not found under {root}")
        if reference not in directories:
            directories.append(reference)
    for directory in directories:
        model = directory / "model"
        if not model.is_dir():
            continue
        case_stem = stem
        metadata = directory / "scenario.json"
        if case_stem is None and metadata.is_file():
            case_stem = json.loads(metadata.read_text(encoding="utf-8")).get("case_metadata", {}).get("case_stem")
        if case_stem is None:
            candidates = sorted(model.glob("*.SMSPEC"))
            if not candidates:
                message = f"{directory.name}: no SMSPEC summary file found"
                if directory.name == reference_case:
                    raise ValueError(message)
                LOGGER.warning("%s; skipping case (run may not have started)", message)
                continue
            if len(candidates) != 1:
                raise ValueError(f"{directory.name}: expected one SMSPEC, found {len(candidates)}; use --summary-stem")
            case_stem = candidates[0].stem
        if not isinstance(case_stem, str) or not case_stem or Path(case_stem).name != case_stem:
            raise ValueError(f"{directory.name}: summary stem must be a file stem, not a path")
        prefix = model / case_stem
        missing = [Path(f"{prefix}{suffix}") for suffix in (".SMSPEC", ".UNSMRY", ".INIT") if not Path(f"{prefix}{suffix}").is_file()]
        if missing:
            message = f"{directory.name}: required output file(s) not found: {', '.join(map(str, missing))}"
            if directory.name == reference_case:
                raise ValueError(message)
            LOGGER.warning("%s; skipping incomplete case (run may not have started)", message)
            continue
        with closing(ResdataFile(f"{prefix}.INIT")) as init:
            if zonation not in init:
                raise ValueError(f"{directory.name}: {zonation} zonation was not found in INIT")
            regions = {int(value) for array in init[zonation] for value in array if value > 0}
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="The StringList class is deprecated", category=DeprecationWarning)
                summary = Summary.load(smspec_file=f"{prefix}.SMSPEC", unsmry_file=f"{prefix}.UNSMRY")
        except OSError as exc:
            raise OSError(f"{directory.name}: cannot load summary {prefix}: {exc}") from exc
        keys = {str(key) for key in summary.keys() if pair_pattern.fullmatch(str(key))}
        if not keys:
            LOGGER.warning("%s: no %s pair vectors found; skipping case (run may not have started)", directory.name, keyword)
            continue
        for key in keys:
            check_regions(directory.name, regions, zonation, key)
        units = {summary.unit(key).strip() for key in keys}
        if len(units) != 1 or not next(iter(units)):
            raise ValueError(f"{directory.name}: inconsistent or missing units for {keyword}")
        unit = units.pop()
        scale = 1.0
        if mass and quantity in ("RGFR", "RGFT", "RWFR", "RWFT"):
            is_rate = quantity.endswith("FR")
            phase = "GAS" if quantity.startswith("RG") else "WATER"
            expected = "M^3/D" if is_rate else "M^3"
            if unit.upper() != expected:
                raise ValueError(f"{directory.name}: {phase.lower()} mass conversion requires {expected}, found {unit!r}")
            scale = surface_density(Path(f"{prefix}.in"), phase)
            unit = "kg/day" if is_rate else "kg"
        if cases and unit != cases[0].unit:
            raise ValueError(f"{directory.name}: unit {unit!r} differs from {cases[0].unit!r}")
        dates = summary.numpy_dates
        if dates.size == 0 or np.isnat(dates).any() or np.any(dates[1:] < dates[:-1]):
            raise ValueError(f"{directory.name}: summary dates are empty, invalid, or decreasing")
        cases.append(Case(directory.name, summary, regions, keys, unit, scale, load_inputs(directory)))
    if not cases:
        raise ValueError(f"No case directories with complete outputs and a model directory match {pattern!r} under {root}")
    return cases


def select_vectors(cases: list[Case], zonation: str, quantity: str, requested: list[str] | None) -> list[str]:
    available = set().union(*(case.keys for case in cases))
    if requested is None:
        return sorted(available)
    keyword = f"{quantity}_{zonation[3:]}"
    selected = []
    for value in requested:
        key = value.upper() if ":" in value else f"{keyword}:{value}"
        match = re.fullmatch(rf"{keyword}:([1-9][0-9]*)-([1-9][0-9]*)", key)
        if match is None or match[1] == match[2]:
            raise ValueError(f"Invalid pair {value!r}; expected e.g. 1-2 or {keyword}:1-2")
        if key not in available:
            for case in cases:
                check_regions(case.name, case.regions, zonation, key)
            raise ValueError(f"{key} was not exported; available vectors: {', '.join(sorted(available))}")
        if key not in selected:
            selected.append(key)
    return selected

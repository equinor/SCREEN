import importlib.util
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from resdata import ResDataType
from resdata.resfile import FortIO, ResdataKW
from resdata.summary import Summary

SCRIPT_PATH = Path(__file__).parents[2] / "runscripts/plot_region_fluxes.py"
SPEC = importlib.util.spec_from_file_location("plot_region_fluxes", SCRIPT_PATH)
plot = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(plot)


def write_case(root, name="hole", unit="M^3/D", partition="FIPHOL", pair=True):
    case = root / name
    model = case / "model"
    model.mkdir(parents=True)
    stem = f"well_{name}"
    prefix = model / stem
    (case / "scenario.json").write_text(json.dumps({"case_metadata": {"case_stem": stem}}))
    summary = Summary.writer(str(prefix), datetime(2025, 1, 1), 1, 1, 1)
    summary.add_variable("RGFR_HOL", num=393217 if pair else 425985, unit=unit)
    key = "RGFR_HOL:1-2" if pair else "RGFR_HOL:1-3"
    for step, days, value in ((1, 0, 0), (2, 365, 3.082)):
        summary.add_t_step(step, days)[key] = value
    summary.fwrite()
    for suffix in ("smspec", "unsmry"):
        Path(f"{prefix}.{suffix}").rename(f"{prefix}.{suffix.upper()}")
    init = FortIO(f"{prefix}.INIT", mode=FortIO.WRITE_MODE)
    try:
        # Separate occurrences exercise parent/LGR region discovery.
        for region in (1, 2, 3):
            keyword = ResdataKW(partition, 1, ResDataType.RD_INT)
            keyword[0] = region
            keyword.fwrite(init)
    finally:
        init.close()
    return case, prefix


def test_real_summary_load_and_headless_plot(tmp_path):
    _, prefix = write_case(tmp_path)
    prefixes = plot.discover_prefixes(tmp_path, "*", None)
    assert prefixes == [("hole", prefix)]
    curves = plot.load_curves(prefixes, [plot.parse_vector("RGFR_HOL:1-2")], -1)
    assert len(curves) == 1
    assert curves[0].unit == "M^3/D"
    np.testing.assert_allclose(curves[0].values, [0, -3.082], rtol=1e-6)
    assert curves[0].dates[-1] == np.datetime64("2026-01-01")
    output = tmp_path / "plots" / "hole.png"
    plot.plot_curves(curves, output, -1)
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.parametrize("value", ["RGFR_HOL:0-2", "RGFR_HOL:1-1", "FGPR", "RGFR_HOL:1", "RGFR_HOL:1-2extra"])
def test_invalid_vector(value):
    with pytest.raises(ValueError):
        plot.parse_vector(value)


def test_missing_partition_is_distinguished(tmp_path):
    _, prefix = write_case(tmp_path, partition="FIPLEG")
    with pytest.raises(ValueError, match="FIPHOL zonation was not found"):
        plot.load_curves([("hole", prefix)], [plot.parse_vector("RGFR_HOL:1-2")], 1)


def test_missing_region_lists_available_ids(tmp_path):
    _, prefix = write_case(tmp_path, partition="FIPLEG")
    with pytest.raises(ValueError, match=r"region 9 does not exist in FIPLEG; available regions: \[1, 2, 3\]"):
        plot.load_curves([("hole", prefix)], [plot.parse_vector("RGFR_LEG:9-1")], 1)


def test_existing_regions_missing_pair_does_not_assume_zero(tmp_path):
    _, prefix = write_case(tmp_path, pair=False)
    with pytest.raises(ValueError, match="RGFR_HOL:1-2 was not exported.*no zero flow is assumed"):
        plot.load_curves([("hole", prefix)], [plot.parse_vector("RGFR_HOL:1-2")], 1)


def test_metadata_selects_main_run_not_initialization(tmp_path):
    _, prefix = write_case(tmp_path)
    (prefix.parent / "fip_init.SMSPEC").touch()
    assert plot.discover_prefixes(tmp_path, "*", None) == [("hole", prefix)]


def test_legacy_ambiguity_requires_explicit_stem(tmp_path):
    case, prefix = write_case(tmp_path)
    (case / "scenario.json").unlink()
    assert plot.discover_prefixes(tmp_path, "*", None) == [("hole", prefix)]
    for suffix in (".SMSPEC", ".UNSMRY", ".INIT"):
        (prefix.parent / f"fip_init{suffix}").touch()
    with pytest.raises(ValueError, match="select --summary-stem explicitly"):
        plot.discover_prefixes(tmp_path, "*", None)
    assert plot.discover_prefixes(tmp_path, "*", "fip_init") == [("hole", prefix.parent / "fip_init")]


def test_filter_and_missing_matching_output(tmp_path):
    write_case(tmp_path, name="hole")
    _, sealed = write_case(tmp_path, name="sealed")
    assert plot.discover_prefixes(tmp_path, "sealed", None) == [("sealed", sealed)]
    Path(f"{sealed}.UNSMRY").unlink()
    with pytest.raises(ValueError, match="required output file not found"):
        plot.discover_prefixes(tmp_path, "*", None)


def test_units_must_match_across_cases(tmp_path):
    _, hole = write_case(tmp_path)
    _, other = write_case(tmp_path, name="other", unit="SM3/D")
    with pytest.raises(ValueError, match="unit.*differs"):
        plot.load_curves([("hole", hole), ("other", other)], [plot.parse_vector("RGFR_HOL:1-2")], 1)


def test_cli_reports_missing_partition_without_plot(tmp_path, monkeypatch, capsys):
    write_case(tmp_path, partition="FIPLEG")
    output = tmp_path / "invalid.png"
    monkeypatch.setattr(
        "sys.argv",
        [
            str(SCRIPT_PATH), "--output-root", str(tmp_path), "--zonation", "FIPHOL",
            "--vector", "1-2", "--output", str(output),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        plot.main()
    assert exc.value.code == 2
    assert "FIPHOL zonation was not found" in capsys.readouterr().err
    assert not output.exists()


def test_inventory_uses_only_exported_pair_directions(tmp_path):
    _, hole = write_case(tmp_path)
    _, sealed = write_case(tmp_path, name="sealed", pair=False)
    _, availability = plot.available_vectors([("hole", hole), ("sealed", sealed)], "FIPHOL", "RGFR")
    assert availability == {"RGFR_HOL:1-2": ["hole"], "RGFR_HOL:1-3": ["sealed"]}
    assert "RGFR_HOL:2-1" not in availability


def test_cli_list_does_not_require_output(tmp_path, monkeypatch, capsys):
    write_case(tmp_path)
    monkeypatch.setattr(
        "sys.argv", [str(SCRIPT_PATH), "--output-root", str(tmp_path), "--zonation", "FIPHOL", "--list-vectors"],
    )
    plot.main()
    text = capsys.readouterr().out
    assert "RGFR_HOL:1-2 | cases: hole" in text
    assert "RGFR_HOL:2-1" not in text


def test_cli_saves_selected_plot(tmp_path, monkeypatch, capsys):
    write_case(tmp_path)
    output = tmp_path / "plots" / "flux.png"
    monkeypatch.setattr(
        "sys.argv",
        [
            str(SCRIPT_PATH), "--output-root", str(tmp_path), "--zonation", "FIPHOL",
            "--vector", "1-2", "--sign", "-1", "--output", str(output),
        ],
    )
    plot.main()
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert "1 cases, 1 vectors" in capsys.readouterr().out


@pytest.mark.parametrize("selection", [["--all"], ["--vector", "1-2"]])
def test_cli_omits_missing_curves_with_warning(tmp_path, monkeypatch, caplog, selection):
    write_case(tmp_path)
    write_case(tmp_path, name="sealed", pair=False)
    plotted = []
    monkeypatch.setattr(plot, "plot_curves", lambda curves, *_args: plotted.extend(curves))
    monkeypatch.setattr(
        "sys.argv",
        [
            str(SCRIPT_PATH), "--output-root", str(tmp_path), "--zonation", "FIPHOL",
            "--output", str(tmp_path / "flux.png"), *selection,
        ],
    )
    plot.main()
    assert ("hole", "RGFR_HOL:1-2") in [(curve.case_name, curve.vector) for curve in plotted]
    assert ("sealed", "RGFR_HOL:1-2") not in [(curve.case_name, curve.vector) for curve in plotted]
    assert "sealed: RGFR_HOL:1-2 was not exported; curve omitted (not assumed zero)" in caplog.text


@pytest.mark.parametrize(
    ("zonation", "pair", "message"),
    [("FIPHOL", "2-1", "was not exported; available vectors"), ("FIPHOL", "9-1", "region 9 does not exist")],
)
def test_cli_rejects_unavailable_selection(tmp_path, monkeypatch, capsys, zonation, pair, message):
    write_case(tmp_path)
    monkeypatch.setattr(
        "sys.argv",
        [
            str(SCRIPT_PATH), "--output-root", str(tmp_path), "--zonation", zonation,
            "--vector", pair, "--output", str(tmp_path / "invalid.png"),
        ],
    )
    with pytest.raises(SystemExit) as exc:
        plot.main()
    assert exc.value.code == 2
    assert message in capsys.readouterr().err
    assert not (tmp_path / "invalid.png").exists()

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


def write_case(root, name="hole", unit="M^3/D", partition="FIPHOL", pair=True, quantity="RGFR"):
    case = root / name
    model = case / "model"
    model.mkdir(parents=True)
    prefix = model / f"well_{name}"
    (case / "scenario.json").write_text(json.dumps({"case_metadata": {"case_stem": prefix.name}}))
    summary = Summary.writer(str(prefix), datetime(2025, 1, 1), 1, 1, 1)
    summary.add_variable(f"{quantity}_HOL", num=393217 if pair else 425985, unit=unit)
    key = f"{quantity}_HOL:{'1-2' if pair else '1-3'}"
    for step, days, value in ((1, 0, 0), (2, 365, 3.082)):
        summary.add_t_step(step, days)[key] = value
    summary.fwrite()
    for suffix in ("smspec", "unsmry"):
        Path(f"{prefix}.{suffix}").rename(f"{prefix}.{suffix.upper()}")
    init = FortIO(f"{prefix}.INIT", mode=FortIO.WRITE_MODE)
    try:
        for region in (1, 2, 3):
            keyword = ResdataKW(partition, 1, ResDataType.RD_INT)
            keyword[0] = region
            keyword.fwrite(init)
    finally:
        init.close()
    return case, prefix


def run_cli(monkeypatch, root, *args):
    monkeypatch.setattr("sys.argv", [str(SCRIPT_PATH), "--output-root", str(root), "--zonation", "FIPHOL", *args])
    plot.main()


def test_list_exact_exported_pairs_and_case_availability(tmp_path, monkeypatch, capsys):
    write_case(tmp_path)
    write_case(tmp_path, name="sealed", pair=False)
    run_cli(monkeypatch, tmp_path, "--list-vectors")
    assert capsys.readouterr().out == "RGFR_HOL:1-2 | cases: hole\nRGFR_HOL:1-3 | cases: sealed\n"


@pytest.mark.parametrize("selection", [("--all",), ("--vector", "1-2")])
def test_plot_real_summary_with_labelled_zero(tmp_path, monkeypatch, caplog, selection):
    from matplotlib.axes import Axes

    write_case(tmp_path)
    write_case(tmp_path, name="sealed", pair=False)
    original = Axes.plot
    curves = {}

    def capture(self, dates, values, **kwargs):
        curves[kwargs["label"]] = (dates, values, kwargs["linestyle"])
        return original(self, dates, values, **kwargs)

    monkeypatch.setattr(Axes, "plot", capture)
    output = tmp_path / "plots" / "flux.png"
    run_cli(monkeypatch, tmp_path, *selection, "--sign", "-1", "--output", str(output))
    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    if selection[0] == "--vector":
        dates, values, style = curves["hole"]
        np.testing.assert_allclose(values, [0, -3.082], rtol=1e-6)
        assert dates[-1] == np.datetime64("2026-01-01")
        assert style == "-"
        _, values, style = curves["sealed (inferred zero)"]
        np.testing.assert_array_equal(values, [0, 0])
        assert style == "--"
    assert "zero direct transfer inferred" in caplog.text


@pytest.mark.parametrize(
    ("pair", "message"),
    [("2-1", "was not exported"), ("9-1", "region 9 does not exist"), ("0-2", "Invalid pair"),
     ("1-1", "Invalid pair"), ("RWFR_LEG:1-2", "Invalid pair")],
)
def test_invalid_selection(tmp_path, monkeypatch, capsys, pair, message):
    write_case(tmp_path)
    output = tmp_path / "invalid.png"
    with pytest.raises(SystemExit) as exc:
        run_cli(monkeypatch, tmp_path, "--vector", pair, "--output", str(output))
    assert exc.value.code == 2
    assert message in capsys.readouterr().err
    assert not output.exists()


def test_missing_partition(tmp_path, monkeypatch, capsys):
    write_case(tmp_path, partition="FIPLEG")
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, tmp_path, "--list-vectors")
    assert "FIPHOL zonation was not found in INIT" in capsys.readouterr().err


def test_missing_quantity_reporting_cannot_infer_zero(tmp_path):
    write_case(tmp_path)
    write_case(tmp_path, name="sealed", quantity="RWFR")
    with pytest.raises(ValueError, match="sealed: FIPHOL exists, but no RGFR_HOL pair vectors confirm reporting"):
        plot.load_cases(tmp_path, "FIPHOL", "RGFR", "*", None)


def test_units_must_match(tmp_path):
    write_case(tmp_path)
    write_case(tmp_path, name="other", unit="SM3/D")
    with pytest.raises(ValueError, match="unit.*differs"):
        plot.load_cases(tmp_path, "FIPHOL", "RGFR", "*", None)


def test_metadata_and_legacy_stem_selection(tmp_path):
    case, prefix = write_case(tmp_path)
    (prefix.parent / "fip_init.SMSPEC").touch()
    assert plot.load_cases(tmp_path, "FIPHOL", "RGFR", "*", None)[0].keys == {"RGFR_HOL:1-2"}
    (case / "scenario.json").unlink()
    with pytest.raises(ValueError, match="use --summary-stem"):
        plot.load_cases(tmp_path, "FIPHOL", "RGFR", "*", None)
    assert plot.load_cases(tmp_path, "FIPHOL", "RGFR", "*", prefix.name)[0].name == "hole"
    Path(f"{prefix}.UNSMRY").unlink()
    with pytest.raises(ValueError, match="required output file not found"):
        plot.load_cases(tmp_path, "FIPHOL", "RGFR", "*", prefix.name)


def test_case_filter_and_missing_cases(tmp_path):
    write_case(tmp_path)
    write_case(tmp_path, name="sealed", pair=False)
    assert [case.name for case in plot.load_cases(tmp_path, "FIPHOL", "RGFR", "sealed", None)] == ["sealed"]
    with pytest.raises(ValueError, match="No case directories"):
        plot.load_cases(tmp_path, "FIPHOL", "RGFR", "absent", None)


@pytest.mark.parametrize(("quantity", "unit"), [("RWFR", "M^3/D"), ("RGFT", "M^3"), ("RWFT", "M^3")])
def test_other_quantities(tmp_path, quantity, unit):
    write_case(tmp_path, quantity=quantity, unit=unit)
    cases = plot.load_cases(tmp_path, "FIPHOL", quantity, "*", None)
    assert plot.select_vectors(cases, "FIPHOL", quantity, None) == [f"{quantity}_HOL:1-2"]
    assert cases[0].unit == unit

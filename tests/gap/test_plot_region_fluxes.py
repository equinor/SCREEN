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
    Path(f"{prefix}.in").write_text("EOS WATER\n SURFACE_DENSITY 1050 kg/m^3\nEND\nEOS GAS\n SURFACE_DENSITY 1.871 kg/m^3\nEND\n")
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
        np.testing.assert_allclose(values, [0, -3.082 * 1.871], rtol=1e-6)
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


@pytest.mark.parametrize(("quantity", "input_unit", "output_unit"), [("RGFR", "M^3/D", "kg/day"), ("RGFT", "M^3", "kg")])
def test_each_case_uses_its_gas_density(tmp_path, quantity, input_unit, output_unit):
    write_case(tmp_path, quantity=quantity, unit=input_unit)
    _, prefix = write_case(tmp_path, name="other", quantity=quantity, unit=input_unit)
    Path(f"{prefix}.in").write_text("EOS GAS\nSURFACE_DENSITY 2.0D+0 kg/m^3 ! test\nEND\n")
    cases = plot.load_cases(tmp_path, "FIPHOL", quantity, "*", None, mass=True)
    assert [case.scale for case in cases] == [1.871, 2.0]
    assert [case.unit for case in cases] == [output_unit, output_unit]


@pytest.mark.parametrize(("quantity", "unit", "label"), [("RGFR", "M^3/D", "kg/day"), ("RGFT", "M^3", "kg")])
def test_mass_plot_values_and_axis_units(tmp_path, monkeypatch, quantity, unit, label):
    from matplotlib.figure import Figure

    write_case(tmp_path, quantity=quantity, unit=unit)
    cases = plot.load_cases(tmp_path, "FIPHOL", quantity, "*", None, mass=True)

    def verify(figure, *_args, **_kwargs):
        assert figure.axes[0].get_ylabel() == label
        np.testing.assert_allclose(figure.axes[0].lines[0].get_ydata(), [0, 3.082 * 1.871], rtol=1e-6)

    monkeypatch.setattr(Figure, "savefig", verify)
    plot.plot_fluxes(cases, [f"{quantity}_HOL:1-2"], "FIPHOL", 1, tmp_path / "mass.png", False)


def test_mass_conversion_rejects_unsupported_volume_units(tmp_path):
    write_case(tmp_path, unit="FT3/D")
    with pytest.raises(ValueError, match="gas mass conversion requires M"):
        plot.load_cases(tmp_path, "FIPHOL", "RGFR", "*", None, mass=True)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("EOS WATER\nSURFACE_DENSITY 1050 kg/m^3\nEND\n", "found 0"),
        ("EOS GAS\nSURFACE_DENSITY 1 g/cm^3\nEND\n", "must use kg/m"),
        ("EOS GAS\nSURFACE_DENSITY -1 kg/m^3\nEND\n", "finite and positive"),
        ("EOS GAS\nSURFACE_DENSITY nan kg/m^3\nEND\n", "finite and positive"),
        ("EOS GAS\nSURFACE_DENSITY abc kg/m^3\nEND\n", "invalid"),
        ("EOS GAS\nSURFACE_DENSITY 1 kg/m^3\nSURFACE_DENSITY 2 kg/m^3\nEND\n", "found 2"),
    ],
)
def test_invalid_gas_density(tmp_path, text, message):
    deck = tmp_path / "case.in"
    deck.write_text(text)
    with pytest.raises(ValueError, match=message):
        plot.gas_surface_density(deck)


def test_volume_option_needs_no_deck(tmp_path, monkeypatch):
    _, prefix = write_case(tmp_path)
    Path(f"{prefix}.in").unlink()
    captured = []
    monkeypatch.setattr(plot, "plot_fluxes", lambda cases, *_args: captured.extend(cases))
    run_cli(monkeypatch, tmp_path, "--all", "--volume", "--output", str(tmp_path / "flux.png"))
    assert captured[0].scale == 1.0
    assert captured[0].unit == "M^3/D"
    with pytest.raises(OSError):
        plot.load_cases(tmp_path, "FIPHOL", "RGFR", "*", None, mass=True)


def test_water_is_not_converted_with_co2_density(tmp_path):
    _, prefix = write_case(tmp_path, quantity="RWFR")
    Path(f"{prefix}.in").unlink()
    case = plot.load_cases(tmp_path, "FIPHOL", "RWFR", "*", None, mass=True)[0]
    assert case.scale == 1.0
    assert case.unit == "M^3/D"


def _case(name, **inputs):
    return plot.Case(name, None, set(), set(), "kg", 1.0, inputs or None)


def test_changed_labels_keep_only_varying_inputs_sorted_numerically():
    cases = [
        _case("c", cb_perm=50.0, casing_hole_open=True, top_depth=4),
        _case("a", cb_perm=1600.0, casing_hole_open=True, top_depth=4),
        _case("b", cb_perm=5.0, casing_hole_open=False, top_depth=4),
        _case("d", cb_perm=None, casing_hole_open=True, top_depth=4),
    ]
    ordered, labels, title = plot.case_labels(cases, "changed")
    assert [case.name for case in ordered] == ["b", "c", "a", "d"]
    assert labels == [
        "cb_perm=5, hole_open=False", "cb_perm=50, hole_open=True", "cb_perm=1600, hole_open=True", "cb_perm=default, hole_open=True",
    ]
    assert title == "Varied: cb_perm, hole_open"


def test_changed_labels_fall_back_to_case_names(caplog):
    same = [_case("a", cb_perm=5.0), _case("b", cb_perm=5.0)]
    for cases in (same, [_case("a", cb_perm=5.0), _case("b")], [_case("a", cb_perm=5.0)]):
        ordered, labels, title = plot.case_labels(cases, "changed")
        assert ordered == cases and labels == [case.name for case in cases] and title is None
    assert plot.case_labels(same, "case")[1:] == (["a", "b"], None)
    assert "using case names" in caplog.text


def test_plot_legend_is_outside_with_changed_labels_and_one_inferred_zero_entry(tmp_path, monkeypatch):
    from matplotlib.figure import Figure

    for name, cb, pair in (("hole", 50.0, True), ("sealed", 5000.0, False)):
        case, _ = write_case(tmp_path, name=name, pair=pair)
        record = json.loads((case / "scenario.json").read_text())
        (case / "scenario.json").write_text(json.dumps({**record, "case_name": name, "cb_perm": cb}))
    legends = []
    original = Figure.legend

    def capture(self, *args, **kwargs):
        legends.append((kwargs["loc"], kwargs["title"], [handle.get_label() for handle in kwargs["handles"]]))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Figure, "legend", capture)
    output = tmp_path / "labels.png"
    run_cli(monkeypatch, tmp_path, "--vector", "1-2", "--label-mode", "changed", "--output", str(output))
    assert output.read_bytes().startswith(b"\x89PNG")
    assert legends == [("outside right center", "Varied: cb_perm", ["cb_perm=50", "cb_perm=5000", "inferred zero (pair not exported)"])]

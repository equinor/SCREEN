import importlib.util
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
from resdata import ResDataType
from resdata.resfile import FortIO, ResdataKW
from resdata.summary import Summary

from src.GaP.libs import region_fluxes

SCRIPT_PATH = Path(__file__).parents[2] / "runscripts/plot_region_fluxes.py"
SPEC = importlib.util.spec_from_file_location("plot_region_fluxes", SCRIPT_PATH)
plot = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(plot)

SENSITIVITY_PATH = Path(__file__).parents[2] / "runscripts/plot_region_sensitivity.py"
SENSITIVITY_SPEC = importlib.util.spec_from_file_location("plot_region_sensitivity", SENSITIVITY_PATH)
sensitivity = importlib.util.module_from_spec(SENSITIVITY_SPEC)
assert SENSITIVITY_SPEC.loader is not None
SENSITIVITY_SPEC.loader.exec_module(sensitivity)


def write_case(root, name="hole", unit="M^3/D", partition="FIPHOL", pair=True, quantity="RGFR", regions=(1, 2, 3)):
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
        for region in regions:
            keyword = ResdataKW(partition, 1, ResDataType.RD_INT)
            keyword[0] = region
            keyword.fwrite(init)
    finally:
        init.close()
    return case, prefix


def run_cli(monkeypatch, root, *args):
    monkeypatch.setattr("sys.argv", [str(SCRIPT_PATH), "--output-root", str(root), "--zonation", "FIPHOL", *args])
    plot.main()


def run_sensitivity_cli(monkeypatch, root, *args):
    monkeypatch.setattr("sys.argv", [str(SENSITIVITY_PATH), "--output-root", str(root), "--zonation", "FIPHOL", *args])
    sensitivity.main()


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
        np.testing.assert_allclose(values, [0, -3.082 * 1.871 * 365.25 / 1000], rtol=1e-6)
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


def test_case_without_quantity_vectors_is_skipped(tmp_path, caplog):
    write_case(tmp_path, name="ready")
    write_case(tmp_path, name="sealed", quantity="RWFR")

    cases = plot.load_cases(tmp_path, "FIPHOL", "RGFR", "*", None)

    assert [case.name for case in cases] == ["ready"]
    assert "sealed: no RGFR_HOL pair vectors found; skipping case" in caplog.text


def test_case_without_requested_regions_is_skipped_from_plot(tmp_path, caplog):
    write_case(tmp_path, name="ready")
    write_case(tmp_path, name="other_regions", pair=False, regions=(1, 3, 5))
    cases = plot.load_cases(tmp_path, "FIPHOL", "RGFR", "*", None)
    keys = plot.select_vectors(cases, "FIPHOL", "RGFR", ["1-2"])

    output = tmp_path / "plot.png"
    plot.plot_fluxes(cases, keys, "FIPHOL", 1, output, False)

    assert output.is_file()
    assert "other_regions: RGFR_HOL:1-2 requires regions not present in FIPHOL; skipping case" in caplog.text


@pytest.mark.parametrize("ylim", [(0, 100), (None, 100), (0, None)])
def test_plot_limits_apply_before_save_and_show(tmp_path, monkeypatch, ylim):
    from matplotlib import pyplot as plt
    from matplotlib.figure import Figure

    write_case(tmp_path)
    cases = plot.load_cases(tmp_path, "FIPHOL", "RGFR", "*", None)
    checked = []

    def verify(figure):
        lower, upper = figure.axes[0].get_ylim()
        if ylim[0] is not None:
            assert lower == ylim[0]
        if ylim[1] is not None:
            assert upper == ylim[1]

    def savefig(figure, *_args, **_kwargs):
        verify(figure)
        checked.append("saved")

    def show():
        verify(plt.gcf())
        checked.append("shown")

    monkeypatch.setattr(Figure, "savefig", savefig)
    monkeypatch.setattr(plt, "show", show)
    plot.plot_fluxes(cases, ["RGFR_HOL:1-2"], "FIPHOL", 1, tmp_path / "plot.png", True, ylim=ylim)
    assert checked == ["saved", "shown"]


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
    with pytest.raises(ValueError, match="No case directories"):
        plot.load_cases(tmp_path, "FIPHOL", "RGFR", "*", prefix.name)


def test_incomplete_cases_are_skipped_while_available_cases_load(tmp_path, caplog):
    write_case(tmp_path, name="ready")
    _, pending_prefix = write_case(tmp_path, name="pending")
    Path(f"{pending_prefix}.UNSMRY").unlink()
    write_case(tmp_path, name="not_started")
    for path in (tmp_path / "not_started" / "model").iterdir():
        path.unlink()
    (tmp_path / "not_started" / "scenario.json").unlink()

    cases = plot.load_cases(tmp_path, "FIPHOL", "RGFR", "*", None)

    assert [case.name for case in cases] == ["ready"]
    assert "pending: required output file(s) not found" in caplog.text
    assert "not_started: no SMSPEC summary file found" in caplog.text


def test_incomplete_reference_case_is_not_skipped(tmp_path):
    write_case(tmp_path, name="ready")
    _, prefix = write_case(tmp_path, name="reference")
    Path(f"{prefix}.UNSMRY").unlink()

    with pytest.raises(ValueError, match="reference: required output file"):
        plot.load_cases(tmp_path, "FIPHOL", "RGFR", "*", None, reference_case="reference")


def test_case_filter_and_missing_cases(tmp_path):
    write_case(tmp_path)
    write_case(tmp_path, name="sealed", pair=False)
    assert [case.name for case in plot.load_cases(tmp_path, "FIPHOL", "RGFR", "sealed", None)] == ["sealed"]
    with pytest.raises(ValueError, match="No case directories"):
        plot.load_cases(tmp_path, "FIPHOL", "RGFR", "absent", None)


@pytest.mark.parametrize("pattern", ["sweep_*", "*", "reference"])
def test_reference_is_included_once_regardless_of_pattern(tmp_path, pattern):
    write_case(tmp_path, name="sweep_low")
    write_case(tmp_path, name="reference")
    cases = plot.load_cases(tmp_path, "FIPHOL", "RGFR", pattern, None, reference_case="reference")
    names = [case.name for case in cases]
    assert names.count("reference") == 1
    assert ("sweep_low" in names) == (pattern != "reference")


@pytest.mark.parametrize("reference", ["absent", "../reference", ".", ""])
def test_invalid_reference_fails_explicitly(tmp_path, reference):
    write_case(tmp_path)
    with pytest.raises(ValueError, match="reference|--reference-case"):
        plot.load_cases(tmp_path, "FIPHOL", "RGFR", "*", None, reference_case=reference)


def test_reference_uses_the_same_unit_validation(tmp_path):
    write_case(tmp_path, name="sweep_low")
    write_case(tmp_path, name="reference", unit="SM3/D")
    with pytest.raises(ValueError, match="unit.*differs"):
        plot.load_cases(tmp_path, "FIPHOL", "RGFR", "sweep_*", None, reference_case="reference")


@pytest.mark.parametrize("label_mode", ["case", "changed"])
def test_reference_plot_is_black_with_thinner_sensitivity_lines(tmp_path, monkeypatch, label_mode):
    from matplotlib.figure import Figure

    for name, cb, pair in (("sweep_low", 1.0, True), ("reference", 100.0, False)):
        case, _ = write_case(tmp_path, name=name, pair=pair)
        record = json.loads((case / "scenario.json").read_text())
        (case / "scenario.json").write_text(json.dumps({**record, "cb_perm": cb}))

    def verify(figure, *_args, **_kwargs):
        lines = figure.axes[0].lines
        assert len(lines) == 2
        reference = next(line for line in lines if "(reference)" in line.get_label())
        sensitivity = next(line for line in lines if "(reference)" not in line.get_label())
        assert reference.get_color() == "black"
        assert reference.get_linewidth() > sensitivity.get_linewidth()
        assert reference.get_zorder() > sensitivity.get_zorder()
        assert reference.get_linestyle() == "--"
        assert "inferred zero" in reference.get_label()
        np.testing.assert_array_equal(reference.get_ydata(), [0, 0])
        handles = figure.legends[0].legend_handles
        reference_handle = next(handle for handle in handles if "(reference)" in handle.get_label())
        assert reference_handle.get_color() == "black"
        assert reference_handle.get_linewidth() == reference.get_linewidth()

    monkeypatch.setattr(Figure, "savefig", verify)
    run_cli(
        monkeypatch, tmp_path, "--case-pattern", "sweep_*", "--reference-case", "reference",
        "--vector", "1-2", "--label-mode", label_mode, "--output", str(tmp_path / "reference.png"),
    )


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
        if quantity == "RGFR":
            assert figure.axes[0].get_ylabel() == "tonnes/year"
            np.testing.assert_allclose(figure.axes[0].lines[0].get_ydata(), [0, 3.082 * 1.871 * 365.25 / 1000], rtol=1e-6)
        else:
            assert figure.axes[0].get_ylabel() == label
            np.testing.assert_allclose(figure.axes[0].lines[0].get_ydata(), [0, 3.082 * 1.871], rtol=1e-6)

    monkeypatch.setattr(Figure, "savefig", verify)
    plot.plot_fluxes(cases, [f"{quantity}_HOL:1-2"], "FIPHOL", 1, tmp_path / "mass.png", False)


@pytest.mark.parametrize(
    ("kg_per_day", "expected_scale", "expected_label"),
    [
        (1000.0, 365.25 / 1000, "tonnes/year"),
        (100_000.0, 365.25 / 1_000_000, "kilotonnes/year"),
        (10_000_000.0, 365.25 / 1_000_000_000, "megatonnes/year"),
    ],
)
def test_annual_mass_rate_auto_selects_metric_prefix(kg_per_day, expected_scale, expected_label):
    scale, label = plot.annual_mass_rate_scale([np.array([0.0, kg_per_day])])
    assert scale == expected_scale
    assert label == expected_label


def test_annual_mass_rate_uses_all_cases_to_select_prefix():
    scale, label = plot.annual_mass_rate_scale([np.array([10.0]), np.array([-1_000_000.0])])
    assert scale == 365.25 / 1_000_000
    assert label == "kilotonnes/year"


@pytest.mark.parametrize(
    ("statistic", "expected"),
    [("last", 5.0), ("min", 0.0), ("max", 8.0), ("mean", 4.25)],
)
def test_summarize_rate_uses_absolute_magnitudes(statistic, expected):
    assert sensitivity.summarize_rate(np.array([0.0, -8.0, 4.0, -5.0]), statistic) == expected


def test_summarize_rate_rejects_empty_or_nonfinite_values():
    with pytest.raises(ValueError, match="finite values"):
        sensitivity.summarize_rate(np.array([]), "last")
    with pytest.raises(ValueError, match="finite values"):
        sensitivity.summarize_rate(np.array([np.nan]), "mean")


@pytest.mark.parametrize(
    ("days", "values", "expected"),
    [
        ([0, 7, 14, 21, 30], [100, 100, 100, 100, 100], True),
        ([0, 7, 14, 21, 30], [-100, -100, -100, -100, -100], True),
        ([0, 7, 14, 21, 30], [99.5, 100, 100, 100, 100.5], True),
        ([0, 7, 14, 21, 30], [99, 100, 100, 100, 101], False),
        ([0, 7, 14, 21, 30], [100, 100, 110, 100, 100], False),
        ([0, 7, 14, 21, 30], [0, 0, 0, 0, 0], True),
        ([0, 7, 14, 21, 30], [0, 0, 0, 0, 1e-12], False),
        ([0, 7, 14, 21, 29], [100, 100, 100, 100, 100], False),
        ([0, 10, 20, 30], [100, 100, 100, 100], False),
        ([0, 0, 10, 20, 30], [100, 100, 100, 100, 100], False),
        ([0, 31, 38, 45, 52, 61], [0, 100, 100, 100, 100, 100], True),
        ([0, 32, 38, 45, 52, 61], [0, 100, 100, 100, 100, 100], False),
    ],
)
def test_rate_plateau_requires_stable_tail_and_time_coverage(days, values, expected):
    dates = np.datetime64("2025-01-01") + np.array(days, dtype="timedelta64[D]")
    assert sensitivity.has_rate_plateau(np.array(values, dtype=float), dates) is expected


def test_sensitivity_plateau_skips_unsettled_cases_and_keeps_last_magnitude(caplog):
    from types import SimpleNamespace

    key = "RGFR_LEG:1-6"
    dates = np.datetime64("2025-01-01") + np.array([0, 7, 14, 21, 30], dtype="timedelta64[D]")

    def case(name, values):
        return plot.Case(
            name, SimpleNamespace(numpy_dates=dates, numpy_vector=lambda _key: np.array(values)),
            {1, 6}, {key}, "kg/day", 2.0, {"permx": 10.0},
        )

    stable = case("stable", [-100, -100, -100, -100, -100])
    unsettled = case("unsettled", [10, 20, 30, 40, 50])
    rows = sensitivity.sensitivity_rows([stable, unsettled], key, "permx", "plateau", "FIPLEG")
    assert rows == [(stable, 10.0, 200.0)]
    assert "unsettled: RGFR_LEG:1-6 has no plateau" in caplog.text
    assert len(sensitivity.sensitivity_rows([stable, unsettled], key, "permx", "last", "FIPLEG")) == 2
    with pytest.raises(ValueError, match="No selected cases.*passed the plateau check"):
        sensitivity.sensitivity_rows([unsettled], key, "permx", "plateau", "FIPLEG")


def test_sensitivity_plateau_rejects_unordered_dates():
    from types import SimpleNamespace

    key = "RGFR_LEG:1-6"
    dates = np.array(["2025-01-01", "2025-02-01", "2025-01-15"], dtype="datetime64[D]")
    case = plot.Case(
        "unordered", SimpleNamespace(numpy_dates=dates, numpy_vector=lambda _key: np.ones(3)),
        {1, 6}, {key}, "kg/day", 1.0, {"permx": 10.0},
    )
    with pytest.raises(ValueError, match="unordered: invalid dates"):
        sensitivity.sensitivity_rows([case], key, "permx", "plateau", "FIPLEG")


def test_sensitivity_cli_reports_no_plateau_without_writing_plot(tmp_path, monkeypatch, capsys, caplog):
    case_dir, _ = write_case(tmp_path)
    record_path = case_dir / "scenario.json"
    record_path.write_text(json.dumps({**json.loads(record_path.read_text()), "cb_perm": 0.1}))
    output = tmp_path / "plateau.png"
    with pytest.raises(SystemExit) as exc:
        run_sensitivity_cli(
            monkeypatch, tmp_path, "--vector", "1-2", "--x-parameter", "cb_perm",
            "--rate-stat", "plateau", "--output", str(output),
        )
    assert exc.value.code == 2
    assert "passed the plateau check" in capsys.readouterr().err
    assert "has no plateau" in caplog.text
    assert not output.exists()


def test_sensitivity_plot_aggregates_rate_and_highlights_reference(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from matplotlib.figure import Figure

    key = "RGFR_LEG:1-6"
    dates = np.array(["2025-01-01", "2025-07-01", "2026-01-01"], dtype="datetime64[D]")
    cases = [
        plot.Case(
            "low", SimpleNamespace(numpy_dates=dates, numpy_vector=lambda _key: np.array([0.0, -4.0, 2.0])),
            {1, 6}, {key}, "kg/day", 2.0, {"permx": 10.0},
        ),
        plot.Case(
            "smeaheia_reference",
            SimpleNamespace(numpy_dates=dates, numpy_vector=lambda _key: np.array([0.0, 5.0, -3.0])),
            {1, 6}, {key}, "kg/day", 1.0, {"permx": 100.0},
        ),
    ]
    captured = {}

    def savefig(figure, *_args, **_kwargs):
        ax = figure.axes[0]
        captured["ylabel"] = ax.get_ylabel()
        captured["collections"] = ax.collections
        captured["labels"] = [legend.get_text() for legend in ax.get_legend().get_texts()]

    monkeypatch.setattr(Figure, "savefig", savefig)
    rows = sensitivity.sensitivity_rows(cases, key, "permx", "max", "FIPLEG")
    sensitivity.plot_sensitivity(
        rows, key, "permx", "max", "smeaheia_reference",
        tmp_path / "sensitivity.png", False, "log", "linear", None, (8, 5), None,
    )
    assert captured["ylabel"] == "Max rate magnitude (tonnes/year)"
    assert captured["labels"] == ["Sensitivity", "Reference"]
    np.testing.assert_allclose(captured["collections"][0].get_offsets(), [[10.0, 4.0 * 2.0 * 365.25 / 1000]])
    np.testing.assert_allclose(captured["collections"][1].get_offsets(), [[100.0, 5.0 * 365.25 / 1000]])


def test_sensitivity_plot_preserves_caller_axis_and_shared_units(tmp_path, monkeypatch):
    import matplotlib
    from matplotlib import pyplot as plt

    case = plot.Case("sweep", None, {1, 6}, {"RGFR_LEG:1-6"}, "kg/day")
    fig, ax = plt.subplots()

    def reject_backend_change(*_args, **_kwargs):
        pytest.fail("Plotting into a caller-owned axis must not change its backend")

    monkeypatch.setattr(matplotlib, "use", reject_backend_change)
    try:
        output = tmp_path / "not_saved_by_helper.png"
        sensitivity.plot_sensitivity(
            [(case, 10.0, 100.0)], "RGFR_LEG:1-6", "permx", "last", None,
            output, False, "linear", "linear", None, (8, 5), None,
            ax=ax, rate_scale=(365.25 / 1_000_000, "kilotonnes/year"),
        )
        assert plt.fignum_exists(fig.number)
        assert not output.exists()
        assert ax.get_ylabel() == "Last rate magnitude (kilotonnes/year)"
        np.testing.assert_allclose(ax.collections[0].get_offsets(), [[10.0, 100.0 * 365.25 / 1_000_000]])
        ax.set_xlim(5, 15)
        assert ax.get_xlim() == (5, 15)
    finally:
        plt.close(fig)


def test_sensitivity_cli_reuses_case_inputs_and_mass_conversion(tmp_path, monkeypatch, capsys):
    case_dir, _ = write_case(tmp_path, name="sweep_low")
    record_path = case_dir / "scenario.json"
    record = json.loads(record_path.read_text())
    record_path.write_text(json.dumps({**record, "cb_perm": 0.1}))
    output = tmp_path / "sensitivity.png"

    run_sensitivity_cli(
        monkeypatch, tmp_path, "--vector", "1-2", "--x-parameter", "cb_perm",
        "--rate-stat", "max", "--output", str(output),
    )

    assert output.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    assert "Saved" in capsys.readouterr().out


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
        region_fluxes.gas_surface_density(deck)


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


@pytest.mark.parametrize(("quantity", "summary_unit", "output_unit"), [("RWFR", "M^3/D", "kg/day"), ("RWFT", "M^3", "kg")])
def test_water_uses_water_surface_density(tmp_path, quantity, summary_unit, output_unit):
    _, prefix = write_case(tmp_path, quantity=quantity, unit=summary_unit)
    case = plot.load_cases(tmp_path, "FIPHOL", quantity, "*", None, mass=True)[0]
    assert case.scale == 1050.0
    assert case.unit == output_unit


@pytest.mark.parametrize("phase", ["GAS", "WATER"])
def test_surface_density_reads_only_requested_eos_block(tmp_path, phase):
    deck = tmp_path / "case.in"
    deck.write_text(
        "EOS WATER\n SURFACE_DENSITY 1050.0 kg/m^3\nEND\n"
        "EOS GAS\n SURFACE_DENSITY 1.871 kg/m^3\nEND\n"
    )
    expected = 1.871 if phase == "GAS" else 1050.0
    assert region_fluxes.surface_density(deck, phase) == expected


@pytest.mark.parametrize(("quantity", "summary_unit"), [("RWFR", "M^3/D"), ("RWFT", "M^3")])
def test_water_mass_plot_values_and_axis_units(tmp_path, monkeypatch, quantity, summary_unit):
    from matplotlib.figure import Figure

    write_case(tmp_path, quantity=quantity, unit=summary_unit)
    cases = plot.load_cases(tmp_path, "FIPHOL", quantity, "*", None, mass=True)

    def verify(figure, *_args, **_kwargs):
        ax = figure.axes[0]
        if quantity == "RWFR":
            assert ax.get_ylabel() == "kilotonnes/year"
            np.testing.assert_allclose(ax.lines[0].get_ydata(), [0, 3.082 * 1050 * 365.25 / 1_000_000])
        else:
            assert ax.get_ylabel() == "kg"
            np.testing.assert_allclose(ax.lines[0].get_ydata(), [0, 3.082 * 1050])

    monkeypatch.setattr(Figure, "savefig", verify)
    plot.plot_fluxes(cases, [f"{quantity}_HOL:1-2"], "FIPHOL", 1, tmp_path / "water.png", False)


def test_water_mass_conversion_rejects_missing_water_density(tmp_path):
    _, prefix = write_case(tmp_path, quantity="RWFR")
    Path(f"{prefix}.in").write_text("EOS GAS\nSURFACE_DENSITY 1.871 kg/m^3\nEND\n")
    with pytest.raises(ValueError, match="EOS WATER SURFACE_DENSITY"):
        plot.load_cases(tmp_path, "FIPHOL", "RWFR", "*", None, mass=True)


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

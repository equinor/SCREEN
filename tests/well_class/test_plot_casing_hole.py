import matplotlib
import pytest

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from src.GaP.libs.models.casing_hole import CasingHole
from src.WellClass.libs.plotting import plot_one_page
from src.WellClass.libs.plotting.plot_sketch import plot_sketch
from src.WellClass.libs.utils import xlsx_to_well_model
from src.WellClass.libs.well_class.well_processed import WellProcessed
from src.WellClass.libs.well_pressure import Pressure

WORKBOOK = "test_data/examples/smeaheia/smeaheia_workbook.xlsx"
HOLE = CasingHole(casing="Casing 13 3/8 in", depth_mTVDMSL=650.0, diameter_m=0.2)


@pytest.fixture(scope="module")
def well():
    return WellProcessed.from_pydantic(xlsx_to_well_model(WORKBOOK))


def _hole_labels(ax):
    return [t.get_text() for t in ax.texts if t.get_text().startswith("Casing hole")]


def test_sketch_marks_casing_hole(well):
    fig, ax = plt.subplots()
    plot_sketch(well, ax=ax, casing_hole=HOLE)
    assert _hole_labels(ax) == ["Casing hole, Casing 13 3/8 in\n650 m TVDMSL, \u00d8 20 cm"]
    plt.close(fig)


def test_sketch_without_casing_hole_has_no_marker(well):
    fig, ax = plt.subplots()
    plot_sketch(well, ax=ax)
    assert _hole_labels(ax) == []
    plt.close(fig)


def test_sketch_rejects_unknown_casing(well):
    fig, ax = plt.subplots()
    with pytest.raises(ValueError, match="exactly one casing"):
        plot_sketch(well, ax=ax, casing_hole=CasingHole(casing="nope", depth_mTVDMSL=650.0, diameter_m=0.2))
    plt.close(fig)


def test_one_page_marks_casing_hole(well):
    pressure = Pressure(header=well.header, co2_datum=1282.5, ground_temperature=4.0, geothermal_gradient=31.0, fluid_type="co2", salinity=0.032)
    fig, (ax_well, _) = plot_one_page(well, pressure, casing_hole=HOLE)
    assert len(_hole_labels(ax_well)) == 1
    plt.close(fig)


@pytest.fixture
def pressure(well):
    return Pressure(header=well.header, co2_datum=1282.5, ground_temperature=4.0, geothermal_gradient=31.0, fluid_type="co2", salinity=0.032)


def test_one_page_depth_axis_ends_at_fluid_contact_plus_buffer(well, pressure):
    fig, (ax_well, ax_pressure) = plot_one_page(well, pressure)
    assert ax_well.get_ylim() == pytest.approx((1382.5, 0.0))
    assert ax_pressure.get_ylim() == pytest.approx((1382.5, 0.0))
    plt.close(fig)


def test_one_page_depth_buffer_is_configurable_and_optional(well, pressure):
    fig, (ax_well, _) = plot_one_page(well, pressure, depth_buffer=50.0)
    assert ax_well.get_ylim() == pytest.approx((1332.5, 0.0))
    plt.close(fig)

    fig, (ax_well, _) = plot_one_page(well, pressure, depth_buffer=None)
    assert ax_well.get_ylim()[0] == pytest.approx(float(pressure.table.depth.max()))
    plt.close(fig)


def test_one_page_pressure_axis_fits_visible_interval(well, pressure):
    fig, (_, ax_pressure) = plot_one_page(well, pressure)
    assert ax_pressure.get_xlim()[1] < 300
    plt.close(fig)

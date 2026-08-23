import numpy as np
import pytest

from src.WellClass.libs.well_pressure.pressure_table import PressureTable


def test_pressure_table_computes_temperature_hydrostatic_and_shmin():
    table = PressureTable(
        name="test",
        depth=np.arange(0.0, 1001.0, 100.0),
        ground_elevation=100.0,
        ground_temperature=4.0,
        geothermal_gradient=40.0,
        shmin_data=[[200.0, 5.0], [500.0, 15.0], [1000.0, 25.0]],
    )

    assert table.temperature[0] == 4.0
    assert table.temperature[-1] == 40.0
    assert np.all(np.diff(table.hydrostatic_pressure) > 0)
    assert table.min_horizontal_stress[2] == 5.0


def test_pressure_table_interpolates_values_at_depth():
    table = PressureTable(
        name="test",
        depth=np.array([0.0, 100.0, 200.0]),
        ground_elevation=100.0,
        ground_temperature=4.0,
        geothermal_gradient=40.0,
        shmin_data=[[200.0, 10.0]],
    )

    values = table.get_values_at_depth(150.0)

    assert set(values) == {"temperature", "hydrostatic_pressure", "min_horizontal_stress"}
    assert values["temperature"] == 6.0
    assert values["min_horizontal_stress"] == pytest.approx(10.55704975)
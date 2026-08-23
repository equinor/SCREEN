import numpy as np

from src.WellClass.libs.pvt.pvt import default_pvt_path, get_hydrostatic_P, get_pvt


def canonical_header():
    return {
        "depth_reference_rkb": 27.0,
        "total_depth_rkb": 4739.0,
        "sf_depth_msl": 99.0,
        "sf_temp": 4.0,
        "geo_tgrad": 40.0,
    }


def test_get_pvt_loads_bundled_tables():
    temperatures, pressures, rho_co2, rho_brine = get_pvt()

    assert default_pvt_path().is_dir()
    assert temperatures.ndim == 1
    assert pressures.ndim == 1
    assert rho_co2.shape == (len(pressures), len(temperatures))
    assert rho_brine.shape == rho_co2.shape
    assert np.all(rho_brine > 0)


def test_hydrostatic_pressure_accepts_canonical_header():
    table = get_hydrostatic_P(canonical_header(), dz=100)

    assert list(table.columns) == ["depth_msl", "temp", "hs_p"]
    assert table.iloc[0]["depth_msl"] == 0.0
    assert np.all(np.diff(table["hs_p"]) > 0)
    assert table.iloc[-1]["depth_msl"] == 5200.0
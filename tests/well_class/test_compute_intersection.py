import numpy as np
import pytest

from src.WellClass.libs.utils.compute_intersection import compute_intersection


def test_compute_intersection_interpolates_crossing():
    x = np.array([0.0, 10.0])
    y1 = np.array([0.0, 10.0])
    y2 = np.array([10.0, 0.0])

    intersect_x, intersect_y = compute_intersection(x, y1, y2)

    assert intersect_x == pytest.approx(5.0)
    assert intersect_y == pytest.approx(5.0)


def test_compute_intersection_returns_nan_without_crossing():
    result = compute_intersection(np.array([0.0, 10.0]), np.array([1.0, 2.0]), np.array([3.0, 4.0]))

    assert np.isnan(result[0])
    assert np.isnan(result[1])


def test_compute_intersection_handles_nans_and_exact_endpoints():
    result = compute_intersection(
        np.array([0.0, 10.0, 20.0]),
        np.array([np.nan, 5.0, 10.0]),
        np.array([np.nan, 2.0, 10.0]),
    )

    assert result == (20.0, 10.0)


def test_compute_intersection_requires_matching_shapes():
    with pytest.raises(ValueError, match="same shape"):
        compute_intersection(np.array([0.0, 10.0]), np.array([1.0]), np.array([2.0, 3.0]))

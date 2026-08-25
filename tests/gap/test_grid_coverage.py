import pytest

from src.WellClass.libs.grid_utils import CoarseGridEnvelope
from src.WellClass.libs.grid_utils.coverage import assess_grid_coverage


def test_coverage_report_marks_fully_covered_grid():
    required = CoarseGridEnvelope(10.0, 20.0, 30.0, 40.0, 100.0, 500.0)

    report = assess_grid_coverage(
        required,
        grid_x_min=0.0,
        grid_x_max=30.0,
        grid_y_min=20.0,
        grid_y_max=50.0,
        grid_z_min=0.0,
        grid_z_max=600.0,
        cell_sizes=[10.0, 20.0],
    )

    assert report.covered
    assert report.warnings == ()
    assert report.cell_size_min == 10.0
    assert report.cell_size_max == 20.0


def test_coverage_report_reports_missing_margins():
    required = CoarseGridEnvelope(10.0, 20.0, 30.0, 40.0, 100.0, 500.0)

    report = assess_grid_coverage(
        required,
        grid_x_min=12.0,
        grid_x_max=18.0,
        grid_y_min=35.0,
        grid_y_max=35.0,
        grid_z_min=120.0,
        grid_z_max=450.0,
    )

    assert not report.covered
    assert report.missing_x_min == 2.0
    assert report.missing_x_max == 2.0
    assert report.missing_y_min == 5.0
    assert report.missing_y_max == 5.0
    assert report.missing_z_min == 20.0
    assert report.missing_z_max == 50.0
    assert len(report.warnings) == 6


def test_coverage_report_rejects_invalid_grid_bounds():
    required = CoarseGridEnvelope(0.0, 1.0, 0.0, 1.0, 0.0, 1.0)

    with pytest.raises(ValueError, match="bounds must be ordered"):
        assess_grid_coverage(
            required,
            grid_x_min=1.0,
            grid_x_max=0.0,
            grid_y_min=0.0,
            grid_y_max=1.0,
            grid_z_min=0.0,
            grid_z_max=1.0,
        )
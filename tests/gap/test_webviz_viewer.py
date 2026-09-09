import importlib.util
import shutil
from pathlib import Path
import pytest

from src.GaP.libs.visualization import hexahedron_polygons


def _load_viewer():
    path = Path("runscripts/run_webviz_viewer.py")
    spec = importlib.util.spec_from_file_location("run_webviz_viewer", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_polygons_encode_six_quad_faces_per_cell():
    corners = [[None] * 8 for _ in range(2)]

    polygons = hexahedron_polygons(len(corners))

    assert len(polygons) == 2 * 6 * 5
    assert polygons[:5] == [4, 0, 1, 2, 3]
    assert polygons[-5:] == [4, 11, 8, 12, 15]


def test_viewer_callback_constructs_component_for_installed_webviz(tmp_path):
    source = Path("test_data/examples/wildcat/model")
    model = tmp_path / "baseline" / "model"
    model.mkdir(parents=True)
    for suffix in ("EGRID", "INIT"):
        shutil.copy(source / f"TEMP-0.{suffix}", model / f"TEMP-0.{suffix}")

    app = _load_viewer().create_app(tmp_path)
    callback = next(value for key, value in app.callback_map.items() if key.startswith("viewer.children"))["callback"]
    component = callback.__wrapped__("baseline", "INIT", "PORV", None, 0.001)
    props = component.to_plotly_json()["props"]

    assert component.id == "screen-viewer"
    assert "verticalScale" not in props
    assert props["views"]["viewports"][0]["show3D"] is False
    assert "style" not in props

    client = app.server.test_client()
    response = client.get("/screen-data/baseline/INIT/PORV/7/0.001/points.json")

    assert response.status_code == 200
    assert response.content_type == "application/json"
    points = response.get_json()
    assert len(points) == 0


def test_viewer_callback_ignores_stale_property_and_j_values(tmp_path):
    source = Path("test_data/examples/wildcat/model")
    model = tmp_path / "baseline" / "model"
    model.mkdir(parents=True)
    for suffix in ("EGRID", "INIT"):
        shutil.copy(source / f"TEMP-0.{suffix}", model / f"TEMP-0.{suffix}")

    app = _load_viewer().create_app(tmp_path)
    callback = next(value for key, value in app.callback_map.items() if key.startswith("viewer.children"))["callback"]

    with pytest.raises(Exception) as error:
        callback.__wrapped__("baseline", "INIT", "NOT_A_KEYWORD", 7, 0.001)

    assert error.value.__class__.__name__ == "PreventUpdate"
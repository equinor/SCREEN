from src.GaP.libs.visualization import hexahedron_polygons


def test_polygons_encode_six_quad_faces_per_cell():
    corners = [[None] * 8 for _ in range(2)]

    polygons = hexahedron_polygons(len(corners))

    assert len(polygons) == 2 * 6 * 5
    assert polygons[:5] == [4, 0, 1, 2, 3]
    assert polygons[-5:] == [4, 11, 8, 12, 15]
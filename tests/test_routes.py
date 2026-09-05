import json

import pytest

from geoport.errors import GeoPortError
from geoport.routes import Route, import_locations, speed


def test_geodesic_interpolation_crosses_date_line():
    route = Route.create([[0, 179], [0, -179]])
    assert 220_000 < route.length < 225_000
    lat, lon = route.position(route.length / 2)
    assert abs(lat) < 0.001
    assert abs(abs(lon) - 180) < 0.001
    assert route.position(route.length) == (0, -179)


def test_duplicate_points_and_exact_segment_boundary():
    route = Route.create([[0, 0], [0, 0], [0, 1], [1, 1]])
    assert len(route.points) == 3
    assert route.position(route.distances[1]) == pytest.approx((0, 1))
    with pytest.raises(GeoPortError):
        Route.create([[0, 0], [0, 0]])


@pytest.mark.parametrize("value", [0, -1, 1000, float("inf"), float("nan"), True, "6"])
def test_invalid_speed(value):
    with pytest.raises(GeoPortError):
        speed(value)


def test_custom_fractional_speed():
    assert speed(7.25) == 7.25


def test_geojson_coordinate_order():
    data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"name": "Place"},
                "geometry": {"type": "Point", "coordinates": [-122, 37]},
            },
            {
                "type": "Feature",
                "properties": {"name": "Route"},
                "geometry": {"type": "LineString", "coordinates": [[-122, 37], [-121, 38]]},
            },
        ],
    }
    result = import_locations(json.dumps(data).encode(), "route.geojson")
    assert result["markers"][0]["point"] == (37, -122)
    assert result["routes"][0]["points"] == [(37, -122), (38, -121)]


def test_gpx_segments_remain_separate():
    xml = b"""<gpx version="1.1"><trk><name>Walk</name>
    <trkseg><trkpt lat="1" lon="2"/><trkpt lat="1" lon="3"/></trkseg>
    <trkseg><trkpt lat="40" lon="50"/><trkpt lat="40" lon="51"/></trkseg>
    </trk></gpx>"""
    result = import_locations(xml, "walk.gpx")
    assert len(result["routes"]) == 2
    assert result["routes"][1]["points"][0] == (40, 50)


@pytest.mark.parametrize(
    "content, filename",
    [
        (b"invalid", "test.gpx"),
        (b'{"type":"FeatureCollection","features":[]}', "test.json"),
        (b'<!DOCTYPE gpx [<!ENTITY x "text">]><gpx>&x;</gpx>', "test.gpx"),
    ],
)
def test_bad_import_is_actionable(content, filename):
    with pytest.raises(GeoPortError):
        import_locations(content, filename)

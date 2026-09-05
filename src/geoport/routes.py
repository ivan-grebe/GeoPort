"""Validated coordinates, geodesic interpolation, and GPX/GeoJSON import."""

import bisect
import json
import math
from dataclasses import dataclass

import gpxpy
from defusedxml import ElementTree
from geographiclib.geodesic import Geodesic

from .errors import GeoPortError

MAX_POINTS = 20_000


def number(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise GeoPortError(f"{label} must be a number.")
    if not math.isfinite(value):
        raise GeoPortError(f"{label} must be finite.")
    return float(value)


def coordinate(value) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise GeoPortError("Each coordinate must contain latitude and longitude.")
    lat, lon = number(value[0], "Latitude"), number(value[1], "Longitude")
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise GeoPortError("Latitude must be within ±90 and longitude within ±180.")
    return lat, lon


def speed(value) -> float:
    result = number(value, "Speed")
    if not 0 < result <= 999:
        raise GeoPortError("Speed must be greater than 0 and no more than 999 km/h.")
    return result


@dataclass
class Route:
    points: list[tuple[float, float]]
    distances: list[float]
    lines: list

    @classmethod
    def create(cls, points):
        if not isinstance(points, list) or not 2 <= len(points) <= MAX_POINTS:
            raise GeoPortError(f"A route needs 2–{MAX_POINTS:,} points.")
        clean = []
        for item in points:
            point = coordinate(item)
            if not clean or point != clean[-1]:
                clean.append(point)
        if len(clean) < 2:
            raise GeoPortError("A route needs at least two different points.")
        lines, distances = [], [0.0]
        for start, end in zip(clean, clean[1:], strict=False):
            line = Geodesic.WGS84.InverseLine(*start, *end)
            lines.append(line)
            distances.append(distances[-1] + line.s13)
        return cls(clean, distances, lines)

    @property
    def length(self):
        return self.distances[-1]

    def position(self, distance: float) -> tuple[float, float]:
        if distance <= 0:
            return self.points[0]
        if distance >= self.length:
            return self.points[-1]
        index = bisect.bisect_right(self.distances, distance) - 1
        point = self.lines[index].Position(distance - self.distances[index])
        return point["lat2"], point["lon2"]


def import_locations(content: bytes, filename: str) -> dict:
    routes, markers = [], []

    def add_route(points, name):
        route = Route.create(points)
        routes.append({"name": name or "Imported route", "points": route.points})

    def add_marker(lat, lon, name):
        markers.append({"name": name or "Imported marker", "point": coordinate([lat, lon])})

    try:
        if filename.lower().endswith(".gpx"):
            # Reject entities before handing XML to the existing GPX library.
            ElementTree.fromstring(content)
            gpx = gpxpy.parse(content.decode("utf-8-sig"))
            for track in gpx.tracks:
                for index, segment in enumerate(track.segments):
                    if len(segment.points) >= 2:
                        add_route(
                            [[p.latitude, p.longitude] for p in segment.points],
                            f"{track.name or 'Track'} · segment {index + 1}",
                        )
            for route in gpx.routes:
                add_route([[p.latitude, p.longitude] for p in route.points], route.name)
            for p in gpx.waypoints:
                add_marker(p.latitude, p.longitude, p.name)
        else:
            data = json.loads(content)

            def visit(item, name=""):
                kind = item.get("type")
                if kind == "FeatureCollection":
                    for feature in item["features"]:
                        visit(feature)
                elif kind == "Feature":
                    properties = item.get("properties") or {}
                    visit(item["geometry"], str(properties.get("name", "")))
                elif kind == "Point":
                    lon, lat, *_ = item["coordinates"]
                    add_marker(lat, lon, name)
                elif kind == "LineString":
                    add_route([[p[1], p[0]] for p in item["coordinates"]], name)
                elif kind == "MultiLineString":
                    for index, points in enumerate(item["coordinates"]):
                        add_route([[p[1], p[0]] for p in points], f"{name} · {index + 1}")
                else:
                    raise GeoPortError("Import supports points and routes (GPX or GeoJSON).")

            visit(data)
        if sum(len(r["points"]) for r in routes) + len(markers) > MAX_POINTS:
            raise GeoPortError(f"Import at most {MAX_POINTS:,} points at once.")
        if not routes and not markers:
            raise GeoPortError("No usable routes or markers were found in this file.")
        return {"routes": routes, "markers": markers}
    except GeoPortError:
        raise
    except Exception as exc:
        raise GeoPortError("This file is not valid GPX or GeoJSON.") from exc

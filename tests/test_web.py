import io
import re

import pytest

from geoport.session import SessionRuntime
from geoport.web import create_app

from .fakes import FakeBackend


@pytest.fixture
def client():
    runtime = SessionRuntime(FakeBackend())
    app = create_app(runtime)
    app.config["TESTING"] = True
    with app.test_client() as client:
        html = client.get("/").text
        token = re.search(r'name="geoport-token" content="([^"]+)"', html)[1]
        client.environ_base["HTTP_X_GEOPORT_TOKEN"] = token
        yield client, runtime
    runtime.close()


def test_home_has_no_outbound_dependency(client, monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("Homepage made an external request")

    monkeypatch.setattr("requests.get", unexpected)
    response = client[0].get("/")
    assert response.status_code == 200
    assert b"api.geoport.me" not in response.data


def test_full_location_lifecycle(client):
    http, _ = client
    assert len(http.get("/api/devices").json["devices"]) == 1
    state = http.post("/api/connect", json={"device_id": "test-phone"}).json
    identity = {"session_id": state["session_id"]}
    response = http.post("/api/location", json={**identity, "point": [37, -122]})
    assert response.status_code == 200
    assert response.json["location"] == [37, -122]
    assert http.delete("/api/location", json=identity).json["location"] is None
    assert http.post("/api/disconnect", json=identity).json["status"] == "disconnected"


def test_validation_and_stale_requests_have_http_errors(client):
    http, _ = client
    assert http.post("/api/location", json={"point": [91, 0]}).status_code == 400
    assert http.post("/api/location", json={"point": [0, 0]}).status_code == 409
    assert http.post("/api/connect", json=[]).status_code == 400
    assert http.post("/api/connect", data="text").status_code == 415


def test_mutations_require_local_page_token(client):
    http, _ = client
    response = http.post(
        "/api/connect", json={"device_id": "test-phone"}, headers={"X-GeoPort-Token": ""}
    )
    assert response.status_code == 403
    assert http.get("/api/session").json["status"] == "disconnected"


def test_upload_import_and_size_limit(client):
    http, _ = client
    response = http.post(
        "/api/import",
        data={"file": (io.BytesIO(b'{"type":"Point","coordinates":[-122,37]}'), "place.geojson")},
    )
    assert response.status_code == 200
    assert response.json["markers"][0]["point"] == [37, -122]
    response = http.post(
        "/api/import", data={"file": (io.BytesIO(b"x" * (5 * 1024 * 1024 + 1)), "big.gpx")}
    )
    assert response.status_code == 413


def test_fuel_failure_does_not_break_device_api(client, monkeypatch):
    import requests

    def unavailable(*args, **kwargs):
        assert kwargs["timeout"] == (3, 8)
        raise requests.Timeout()

    monkeypatch.setattr("requests.get", unavailable)
    assert client[0].get("/api/fuel").status_code == 503
    assert client[0].get("/api/devices").status_code == 200

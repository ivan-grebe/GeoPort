"""Local HTTP interface. Handlers validate input; the session owns device state."""

import secrets
import threading
import time
from urllib.parse import urlsplit

import requests
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from . import __version__
from .errors import GeoPortError
from .routes import import_locations


class FuelData:
    def __init__(self):
        self.lock = threading.Lock()
        self.data = None
        self.fetched_at = 0.0

    def prices(self, region):
        with self.lock:
            if self.data is None or time.monotonic() - self.fetched_at > 300:
                try:
                    response = requests.get(
                        "https://projectzerothree.info/api.php?format=json", timeout=(3, 8)
                    )
                    response.raise_for_status()
                    data = response.json()
                    if not isinstance(data.get("regions"), list):
                        raise ValueError("Invalid fuel response")
                    self.data, self.fetched_at = data, time.monotonic()
                except (requests.RequestException, ValueError) as exc:
                    raise GeoPortError(
                        "Fuel prices are unavailable. Location simulation still works.",
                        "fuel_unavailable",
                        503,
                    ) from exc
            return next((r["prices"] for r in self.data["regions"] if r["region"] == region), [])


def create_app(runtime):
    app = Flask(__name__)
    app.config.update(
        MAX_CONTENT_LENGTH=5 * 1024 * 1024, TRUSTED_HOSTS=["localhost", "127.0.0.1", "[::1]"]
    )
    token = secrets.token_urlsafe(32)
    fuel = FuelData()
    app.extensions["geoport_runtime"] = runtime

    @app.before_request
    def require_local_client():
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            if not secrets.compare_digest(request.headers.get("X-GeoPort-Token", ""), token):
                raise GeoPortError("Reload GeoPort before trying again.", "invalid_token", 403)
            origin = request.headers.get("Origin")
            if origin and urlsplit(origin).netloc != request.host:
                raise GeoPortError("Use the GeoPort page opened on this computer.", status=403)

    @app.after_request
    def response_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.errorhandler(GeoPortError)
    def known_error(exc):
        return jsonify(error={"code": exc.code, "message": str(exc)}), exc.status

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return jsonify(error={"code": "http_error", "message": exc.description}), exc.code

    @app.errorhandler(Exception)
    def unexpected_error(exc):
        app.logger.exception("Unexpected application error")
        return jsonify(
            error={
                "code": "internal_error",
                "message": "An unexpected error occurred. Check the terminal log.",
            }
        ), 500

    def body():
        data = request.get_json()
        if not isinstance(data, dict):
            raise GeoPortError("Send a JSON object.")
        return data

    @app.get("/")
    def index():
        # No device discovery, telemetry, updates, IP lookup, or fuel fetch during page load.
        return render_template("map.html", version=__version__, token=token)

    @app.get("/api/devices")
    def devices():
        return jsonify(devices=runtime.call("discover"))

    @app.get("/api/session")
    def status():
        return jsonify(runtime.call("snapshot"))

    @app.post("/api/connect")
    def connect():
        return jsonify(runtime.call("command", "connect", body()))

    @app.post("/api/disconnect")
    def disconnect():
        return jsonify(runtime.call("command", "disconnect", body()))

    @app.route("/api/location", methods=["POST", "DELETE"])
    def location():
        command = "location" if request.method == "POST" else "clear"
        return jsonify(runtime.call("command", command, body()))

    @app.post("/api/playback")
    def play():
        return jsonify(runtime.call("command", "play", body()))

    @app.post("/api/playback/<action>")
    def playback_action(action):
        if action not in {"pause", "resume", "stop"}:
            raise GeoPortError("Unknown playback action.", status=404)
        return jsonify(runtime.call("command", action, body()))

    @app.post("/api/import")
    def import_file():
        upload = request.files.get("file")
        if upload is None:
            raise GeoPortError("Choose a GPX or GeoJSON file.")
        return jsonify(import_locations(upload.read(), upload.filename or ""))

    @app.get("/api/fuel")
    def fuel_prices():
        return jsonify(prices=fuel.prices(request.args.get("region", "All")))

    return app

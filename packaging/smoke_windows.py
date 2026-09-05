"""Verify the executable outside the checkout without accessing device services."""

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

import psutil

from geoport import __version__


def main():
    executable = Path(sys.argv[1]).resolve(strict=True)
    environment = os.environ.copy()
    for name in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        environment.pop(name, None)
    environment["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    with tempfile.TemporaryDirectory(prefix="geoport-smoke-") as directory:
        result = subprocess.run(
            [str(executable), "--version"],
            cwd=directory,
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=True,
        )
        assert result.stdout.strip() == __version__, result
        output = Path(directory) / "startup.log"
        with output.open("w") as log:
            process = subprocess.Popen(
                [str(executable), "--no-browser", "--port", "0"],
                cwd=directory,
                env=environment,
                stdout=log,
                stderr=log,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            try:
                deadline = time.monotonic() + 60
                address = None
                while time.monotonic() < deadline and process.poll() is None:
                    match = re.search(r"http://127\.0\.0\.1:\d+", output.read_text())
                    if match:
                        address = match.group()
                        break
                    time.sleep(0.1)
                assert address, output.read_text()

                def get(path):
                    with urlopen(address + path, timeout=5) as response:
                        assert response.status == 200
                        return response.read()

                assert b"Simulate location" in get("/")
                assert json.loads(get("/api/session"))["status"] == "disconnected"
                for path in (
                    "/static/app.js",
                    "/static/app.css",
                    "/static/vendor/leaflet.js",
                    "/static/vendor/leaflet.css",
                ):
                    assert len(get(path)) > 100
                print("Standalone EXE passed: version, startup, HTTP, templates, CSS, JS, Leaflet.")
                print("No device discovery, pairing, or location operations were performed.")
            finally:
                # One-file PyInstaller owns a child process. Stop only this test's process tree.
                if process.poll() is None:
                    parent = psutil.Process(process.pid)
                    children = parent.children(recursive=True)
                    for child in children:
                        child.kill()
                    psutil.wait_procs(children, timeout=5)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()

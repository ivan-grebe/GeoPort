"""Browser-test server. It has no real device backend and is not shipped in the wheel."""

from waitress import create_server

from geoport.session import SessionRuntime
from geoport.web import create_app

from .fakes import FakeBackend

if __name__ == "__main__":
    runtime = SessionRuntime(FakeBackend())
    server = create_server(create_app(runtime), host="127.0.0.1", port=0)
    print(f"FAKE_DEVICE_URL=http://127.0.0.1:{server.effective_port}", flush=True)
    try:
        server.run()
    finally:
        runtime.close()
        server.close()

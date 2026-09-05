"""Launch the local production WSGI server and its owned device worker."""

import argparse
import logging
import webbrowser

from waitress import create_server

from . import __version__
from .device import MobileDeviceBackend
from .session import SessionRuntime
from .web import create_app


def main():
    parser = argparse.ArgumentParser(description="GeoPort — local iOS location simulation")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--port", type=int, default=54321, help="Local port; 0 selects a free port")
    parser.add_argument("--no-browser", action="store_true", help="Do not open the browser")
    args = parser.parse_args()
    if not 0 <= args.port <= 65535:
        parser.error("port must be between 0 and 65535")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    runtime = SessionRuntime(MobileDeviceBackend())
    server = None
    try:
        server = create_server(create_app(runtime), host="127.0.0.1", port=args.port, threads=4)
        url = f"http://127.0.0.1:{server.effective_port}"
        print(f"GeoPort {__version__}: {url}\nPress Ctrl+C to restore GPS and quit.", flush=True)
        if not args.no_browser:
            try:
                webbrowser.open(url)
            except webbrowser.Error:
                print("Open the address above in your browser.", flush=True)
        server.run()
    except OSError as exc:
        parser.exit(1, f"Cannot start GeoPort: {exc}. Try --port 0 for a free port.\n")
    except KeyboardInterrupt:
        pass
    finally:
        if server:
            server.close()
        runtime.close()


if __name__ == "__main__":
    main()

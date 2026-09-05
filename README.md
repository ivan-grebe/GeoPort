# GeoPort

Simulate locations and routes on your own iPhone from a local browser interface.

This is a development edition of [ivan-grebe/GeoPort](https://github.com/ivan-grebe/GeoPort), based on [davesc63/GeoPort](https://github.com/davesc63/GeoPort). It replaces the original connection lifecycle and UI implementation. It is not an upstream 4.0.2 release.

## Status

The current target is **iOS 17.4+**, using **pymobiledevice3 11.3.0**. The older custom QUIC/driver paths have been removed. Modern iOS support is a target, not a hardware certification: automated tests use a simulated device. Physical USB/Wi-Fi connections, image mounting, and iOS 27 beta behavior still require testing. A portable Windows x64 executable is available from successful Windows CI builds. It is unsigned; installers and signed releases have not been produced.

## Windows executable

Download the **GeoPort-Windows-x64** artifact from a successful [Check workflow run](https://github.com/ivan-grebe/GeoPort/actions/workflows/check.yml) on this branch, extract it, and double-click `GeoPort.exe`. Python, Node.js, and a source checkout are not required. Apple Devices or iTunes must still provide Apple's device connectivity services.

GeoPort opens the interface in your default browser. Keep its console window open while using it. To exit normally, press **Ctrl+C in the console**; GeoPort asks the phone to restore GPS before closing. Closing the browser tab alone does not stop the application. A forced process exit cannot guarantee GPS restoration.

The first launch extracts bundled files and may take several seconds. If the default port is occupied, launch `GeoPort.exe --port 0` from a terminal. `--no-browser` and `--version` are also supported.

## Run from source

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run from this repository:

```sh
uv sync --locked --python 3.12
uv run geoport
```

The app opens `http://127.0.0.1:54321`. If the port is occupied, use `uv run geoport --port 0` to select a free port. Use `--no-browser` to open the printed address yourself.

Python 3.12–3.14 is allowed by the package; local validation used Python 3.12 on Windows. CI is configured for Python 3.12 on Windows, macOS, and Linux.

Before connecting:

- On Windows, install Apple's device connectivity software (Apple Devices or iTunes). On Linux, install and run usbmuxd. macOS includes Apple's device service.
- Unlock the phone, connect USB, and accept **Trust This Computer**.
- Enable **Settings → Privacy & Security → Developer Mode**, complete the restart, and confirm on the phone. Keep your passcode enabled.
- Allow internet access for the initial developer image download and personalization. The app checks for an already mounted image first.

GeoPort uses the library's unprivileged tunnel implementation. It does not elevate the whole app, install third-party drivers, or stop system daemons itself.

## Use

1. Select your device and click **Connect**. Pairing and developer image preparation can take up to a minute.
2. Click the map, search for a place, or enter latitude and longitude. Click **Simulate location**.
3. Draw a route or import GPX/GeoJSON. Choose a speed, including a custom value, and click **Play route**.
4. Use **Pause / Resume** to hold and continue a route. **Restore GPS** cancels playback and asks the device to clear location simulation.
5. Click **Disconnect**, or press Ctrl+C in the terminal to restore GPS and shut down normally.

The outlined point is your selection; the filled point is the last position accepted by the device service. A successful API call does not independently verify what every iOS app displays. If the connection fails, GeoPort stops playback and reports the failure. Reconnect and use **Restore GPS** if a simulated location remains.

Route timing runs on the backend, so background browser tabs do not control movement. Routes follow geodesic segments between supplied points. There is no automatic road routing in this edition. GPX track segments and GeoJSON MultiLineStrings remain separate selectable routes. Imports accept up to 5 MB and 20,000 points. Route timing comes from the selected speed; GPX timestamps and elevation are not replayed.

## Wi-Fi and phone-only use

After connecting by USB, click **Enable Wi-Fi connections**. Disconnect in GeoPort, unplug USB, refresh the device list, and reconnect with both devices on the same local network. The library chooses the transport for the selected device. The list shows available transports, not a promise of seamless USB-to-Wi-Fi handoff.

The computer must remain running and reachable. Sleep, network changes, and OS updates can end a session. This app does not promise persistence after disconnection or operate over cellular by itself.

For the separate investigation into on-device simulation on an iPhone 13 Pro running iOS 27 Public Beta, see [phone-only research](docs/phone-only-research.md).

## Privacy and external services

- No telemetry, device-name uploads, IP geolocation, upstream broadcasts, or automatic update checks.
- Device control binds to loopback only. Mutations require the token issued to the local page.
- Leaflet JavaScript and CSS are bundled locally. Map tiles come from OpenStreetMap; submitted searches go to Nominatim. These services receive the map areas or queries you request.
- Australian fuel data comes from Project Zero Three only when you open that panel. A fuel outage does not prevent device control.
- pymobiledevice3 manages local pairing records. GeoPort caches developer images in its `geoport-ddi` subfolder. Setup can contact the image distribution source and Apple's personalization services.

## Development

```sh
uv run pytest
uv run ruff check src tests
uv run ruff format --check src tests
uv build
```

To build the single Windows executable, run on Windows x64 with Python 3.12:

```sh
uv sync --locked --python 3.12 --group windows-build
uv run --group windows-build pyinstaller --noconfirm packaging/GeoPort.spec
uv run python packaging/smoke_windows.py dist/GeoPort.exe
```

The output is `dist/GeoPort.exe`. The smoke check runs it from a temporary directory with Python-specific environment variables removed and a minimal PATH. It checks startup and bundled web assets without discovering or controlling devices. The recipe uses [PyInstaller's one-file packaging](https://pyinstaller.org/en/stable/spec-files.html).

Browser integration checks need Node.js and Playwright:

```sh
npm ci
npx playwright install chromium
npm run test:browser
```

The browser test starts `tests.browser_server`, which uses only a fake device. It tests connection, coordinates, custom speed, playback, pause/resume, restoration, import/export, errors, mobile layout, and unavailable map assets. It selects a free local port and writes screenshots under `test-results/`.

Python tests explicitly disable the unrelated xonsh pytest plugin pulled in by pymobiledevice3. No hardware is accessed by the automated tests. See [architecture and validation](docs/reliability.md) and [FAQ](FAQ.md).

## Credits

Original GeoPort by [davesc63](https://github.com/davesc63/GeoPort), with this fork maintained at [ivan-grebe/GeoPort](https://github.com/ivan-grebe/GeoPort). Device communication is provided by [pymobiledevice3](https://github.com/doronz88/pymobiledevice3). Maps use [Leaflet](https://leafletjs.com/) and OpenStreetMap data. Interpolation uses GeographicLib; GPX parsing uses gpxpy.

GeoPort retains its [GPL-3.0 license](LICENSE). The bundled Leaflet distribution retains its [license notice](src/geoport/static/vendor/LEAFLET-LICENSE).

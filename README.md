# GeoPort

Simulate an iPhone's location and routes from a local browser interface. Fork of [davesc63/GeoPort](https://github.com/davesc63/GeoPort).

[Downloads](https://github.com/ivan-grebe/GeoPort/releases) · [Issues](https://github.com/ivan-grebe/GeoPort/issues)

## Features

- Set a location using the map, search, or coordinates; restore real GPS when finished.
- Connect and drag route nodes, choose speed in km/h, and pause or resume playback.
- Finish modes: stop, loop a closed route, restart from the beginning, or reverse back and forth.
- Import GPX/GeoJSON and export GeoJSON. Routes follow straight segments between nodes.
- USB and local Wi-Fi connections; Australian fuel prices with state filtering.

![GeoPort](images/geoport.png)

## Requirements

- iOS 17.4+ with **Settings → Privacy & Security → Developer Mode** enabled. Complete the restart and confirmation; keep your passcode enabled.
- If Developer Mode is hidden, connect over USB and click **Connect** in GeoPort to reveal it.
- Windows with Apple Devices or iTunes installed.
- Internet access for initial developer image setup, maps, search, and fuel prices.

## Installation

1. Download and run `GeoPort.exe` from [Releases](https://github.com/ivan-grebe/GeoPort/releases).
2. Connect your iPhone by USB, unlock it, and accept **Trust This Computer**. Keep it awake during setup.
3. At `http://127.0.0.1:54321`, select the device and click **Connect**.
4. Choose a location and click **Simulate location**, or add route nodes and start playback.
5. Use **Restore GPS** when finished. **Ctrl+C** in the console restores GPS and exits.

## App Notes

- Keep GeoPort running on the computer. Closing the browser tab does not stop it.
- For Wi-Fi: click **Enable Wi-Fi connections** while connected by USB, disconnect, unplug, and reconnect on the same network. The computer must remain reachable.
- iOS may restore the real location after unplugging or losing the connection ([#190](https://github.com/davesc63/GeoPort/issues/190)); disconnected simulation is not guaranteed. If simulation remains, reconnect and use **Restore GPS**.
- The EXE is unsigned. USB connection was tested and location simulation confirmed by a user on an iPhone 13 Pro with iOS 27 beta; physical route playback and Wi-Fi remain unverified.

## Tech Stuff and Recognition

Python, Flask, and Waitress serve the local interface and run route playback on the computer.

- [davesc63/GeoPort](https://github.com/davesc63/GeoPort) — original project ([support Dave](https://www.buymeacoffee.com/davesc63)).
- [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) — device communication and location simulation.
- [iFakeLocation](https://github.com/master131/iFakeLocation) — original GeoPort's interface inspiration.
- [Leaflet](https://leafletjs.com/) and [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) — maps; Nominatim provides place search.
- [GeographicLib](https://geographiclib.sourceforge.io/) and [gpxpy](https://github.com/tkrajina/gpxpy) — route interpolation and GPX parsing.
- [Project Zero Three](https://projectzerothree.info/) — Australian fuel prices.

### Run From Source

With Python 3.12, from the repository directory:

```sh
python -m pip install -r requirements.txt
python src/main.py
```

Options: `--port 0` selects a free port; `--no-browser` skips opening the browser; `--version` prints the version. The [release workflow](.github/workflows/release.yml) packages the Windows EXE with PyInstaller.

Licensed under [GPL-3.0](LICENSE).

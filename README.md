# GeoPort

Simulate an iPhone's location and routes from a local browser interface.

Fork of [davesc63/GeoPort](https://github.com/davesc63/GeoPort).

[Release Notes and Downloads](https://github.com/ivan-grebe/GeoPort/releases) · [Report an Issue](https://github.com/ivan-grebe/GeoPort/issues)

## Key Features

- Set a location using the map, place search, or latitude and longitude.
- Create routes with connected, draggable nodes and a configurable speed in km/h.
- Pause and resume playback; stop, loop, restart, or reverse at the end of a route.
- Import GPX and GeoJSON; export GeoJSON.
- Connect over USB or supported local Wi-Fi connections.
- Restore the device's real GPS location.

![GeoPort](images/geoport.png)

## Fuel Mode

Open **Australian fuel prices** to load prices from [Project Zero Three](https://projectzerothree.info/). Filter by state or territory and select a result to choose its coordinates on the map.

Fuel data loads only when the panel is opened. Provider outages do not prevent location simulation.

## Developer Mode

Enable **Settings → Privacy & Security → Developer Mode** on the iPhone, finish the restart, and confirm when prompted. Keep your passcode enabled.

Keep the iPhone unlocked and awake during connection setup. A locked phone can refuse the developer image upload.

## Prerequisites

- An iPhone running **iOS 17.4 or newer**, with Developer Mode enabled.
- **Windows:** Apple Devices or iTunes for Apple's USB connectivity services.
- Internet access for initial developer image setup, map tiles, place searches, and optional fuel prices.
- **Running from source:** Python 3.12.

## Installation

1. Download `GeoPort.exe` from [Releases](https://github.com/ivan-grebe/GeoPort/releases).
2. Run it and keep the console window open. The interface opens at `http://127.0.0.1:54321`.
3. Connect the iPhone by USB, unlock it, and accept **Trust This Computer**.
4. Select the device and click **Connect**.
5. Choose a location and click **Simulate location**.

## App Notes

- This fork's packaged release is for Windows. USB Connect/Disconnect was verified on an iPhone 13 Pro running iOS 27 beta; physical route playback and Wi-Fi remain unverified.
- The Windows executable is unsigned.
- Use **Restore GPS** when finished. Press **Ctrl+C** in the console to restore GPS and shut down normally; closing the browser tab alone leaves GeoPort running.
- If a simulated location remains after disconnection, reconnect and select **Restore GPS**.
- If Connect fails, include the full error from the page and console when reporting the issue.

### Wi-Fi Connections

While connected over USB, click **Enable Wi-Fi connections**. This enables Apple's wireless device connection setting on the phone. Disconnect in GeoPort, unplug USB, and reconnect with the phone and computer on the same local network.

The computer must stay running and reachable. This setting allows wireless communication with the computer; it does not provide cellular or phone-only operation.

### Routes

**Add nodes** connects map clicks in order. Drag nodes to move them or use **Add coordinates**. Click the first node while adding, or check **Connect last node to first**, to close the route. Imports over 200 nodes show draggable endpoints only.

Enter a speed in km/h and choose the finish mode:

- **Stop:** hold the last location.
- **Loop:** follow the closing segment and repeat. Requires connecting the last node to the first.
- **Restart:** jump to the first node and repeat.
- **Reverse:** travel back and forth along the route.

**Pause** holds position; **Restore GPS** ends playback. Loop, restart, and reverse repeat until paused or stopped. Routes follow straight segments between the supplied points; automatic road routing is not included.

## Tech Stuff and Recognition

GeoPort uses Python, Flask and Waitress for the local server, with pymobiledevice3 for device discovery, pairing, developer image mounting, and location simulation. Route playback runs on the computer, including when the browser tab is in the background.

- [davesc63/GeoPort](https://github.com/davesc63/GeoPort) — original project by Dave.
- [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) — Apple device communication.
- [iFakeLocation](https://github.com/master131/iFakeLocation) — interface inspiration acknowledged by the original GeoPort project.
- [Leaflet](https://leafletjs.com/) — map interface.
- [OpenStreetMap contributors](https://www.openstreetmap.org/copyright) — map data; OpenStreetMap also provides map tiles and Nominatim place search.
- [GeographicLib](https://geographiclib.sourceforge.io/) — distance calculations and route interpolation.
- [gpxpy](https://github.com/tkrajina/gpxpy) — GPX parsing.
- [Project Zero Three](https://projectzerothree.info/) — Australian fuel price data.

### Run From Source

From the repository directory, using Python 3.12:

```sh
python -m pip install -r requirements.txt
python src/main.py
```

The server listens on `127.0.0.1` only. Available command-line options:

- `--port 0` — select a free port, or supply a specific port number.
- `--no-browser` — start without opening a browser.
- `--version` — print the application version.

Dependencies are pinned in `requirements.txt`. The [release workflow](.github/workflows/release.yml) builds the Windows executable with PyInstaller and publishes it through GitHub Releases.

Licensed under [GPL-3.0](LICENSE).

## Pay It Forward

Support the original GeoPort developer: [buy davesc63 a beer](https://www.buymeacoffee.com/davesc63).

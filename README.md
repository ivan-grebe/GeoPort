# GeoPort

iPhone location and route simulation.

[Download](https://github.com/ivan-grebe/GeoPort/releases)

![GeoPort](images/geoport.png)

## Features

- Set coordinates using the map or place search.
- Edit route nodes, import GPX/GeoJSON, export GeoJSON, and set playback speed.
- Stop, loop, restart, or reverse at the end of a route.
- USB and local Wi-Fi connections.
- Australian fuel prices.

## Setup

Requires Apple Devices or iTunes on Windows, and Developer Mode on the iPhone. Target: iOS 17.4+.

1. Download and run `GeoPort.exe`.
2. Connect the iPhone by USB, unlock it, and accept **Trust This Computer**.
3. Click **Connect**, select a location, and click **Simulate location**.
4. Use **Restore GPS** to stop simulation. Press **Ctrl+C** in the console to exit.

Keep the phone awake during connection setup. Initial setup requires internet access.

For Wi-Fi, pair over USB and enable Wi-Fi connections, then disconnect and reconnect on the same network. The computer must stay running and reachable.

## Routes

**Add nodes** connects map clicks in order. Drag nodes to move them or use **Add coordinates**. Enter speed in km/h and choose the finish mode:

- **Stop:** hold the last location.
- **Loop:** follow the closing segment and repeat. Requires connecting the last node to the first.
- **Restart:** jump to the first node and repeat.
- **Reverse:** travel back and forth along the route.

**Pause** holds position; **Restore GPS** ends playback. Routes use straight segments, without road routing.

## Source

Python 3.12:

```sh
python -m pip install -r requirements.txt
python src/main.py
```

Local interface: `http://127.0.0.1:54321`. Use `--port 0` for a free port.

## Credits

Fork of [davesc63/GeoPort](https://github.com/davesc63/GeoPort). Device communication uses [pymobiledevice3](https://github.com/doronz88/pymobiledevice3). Maps use Leaflet and OpenStreetMap.

[GPL-3.0](LICENSE).

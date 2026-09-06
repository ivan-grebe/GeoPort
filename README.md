# GeoPort
Simulate an iPhone's location and routes from a local browser interface. Verified working on iOS 27.

[Download here](https://github.com/ivan-grebe/GeoPort/releases)

> [!WARNING]
> On newer iOS versions, the real location may be restored after unplugging or losing the connection. One workaround may be disabling iOS developer mode before disconnecting.
> 
## Features

- Set a location using the map, search, or coordinates; restore real GPS when finished.
- Connect and drag route nodes, follow direction arrows, choose speed in km/h, and pause, resume, or stop playback.
- Finish modes: stop, loop a closed route, restart from the beginning, or reverse back and forth.
- Import GPX/GeoJSON and export GeoJSON. Routes follow straight segments between nodes.
- USB and local Wi-Fi connections; Australian fuel prices with state filtering.

## Requirements

- Windows with Apple Devices or iTunes installed.
- iOS 17.4+ with **Settings → Privacy & Security → Developer Mode** enabled. Complete the restart and confirmation.
  - If Developer Mode is hidden, connect over USB and click **Connect** in GeoPort to reveal it.
- Internet access for initial developer image setup, maps, search, and fuel prices.

## Installation

1. Download and run `GeoPort.exe` from [Releases](https://github.com/ivan-grebe/GeoPort/releases).
2. Connect your iPhone by USB, unlock it, and accept **Trust This Computer**. Keep it awake during setup.
3. At `http://127.0.0.1:54321`, select the device and click **Connect**.
4. Choose a location and click **Simulate location**, or add route nodes and start playback.
5. Use **Restore GPS** when finished. **Ctrl+C** in the console restores GPS and exits.

## Tech Stuff

- [davesc63/GeoPort](https://github.com/davesc63/GeoPort) - original project
- [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) - device communication and location simulation

### Run From Source

With Python 3.12, from the repository directory:

```sh
python -m pip install -r requirements.txt
python src/main.py
```

Options: `--port 0` selects a free port; `--no-browser` skips opening the browser; `--version` prints the version. The [release workflow](.github/workflows/release.yml) packages the Windows EXE with PyInstaller.

Licensed under [GPL-3.0](LICENSE).

# Reliability implementation and validation

Baseline: `d38c7c550512d3d1e0e6c49de59a695d417bc5f0`, shared by the fork and upstream when reviewed on 2026-09-05.

## Architecture

```text
Browser (Leaflet, plain ES module)
    ↓ local JSON API
Flask / Waitress
    ↓ thread-safe coroutine submission
SessionRuntime → one asyncio loop → DeviceSession
    ↓ persistent async context, serialized operations
MobileDeviceBackend → pymobiledevice3 → paired iPhone
```

- `web.py` validates HTTP input and delegates device operations. External fuel fetching is isolated and bounded.
- `session.py` owns one active device, session identity, location channel, playback task, and disconnection watcher. A lock serializes commands. Timeouts discard the session and release its contexts.
- `device.py` contains the pinned dependency's API integration. It checks identity, Developer Mode, and the mounted image, then opens a preferred RSD tunnel, DVT provider, and location channel.
- `images.py` downloads developer images asynchronously into a temporary directory, checks the pinned build, and publishes complete cache entries atomically. Cancellation discards partial downloads. Device acquisition that finishes after cancellation is closed by an owned cleanup task; retries wait for that cleanup, and cleanup failure requires a restart.
- `routes.py` validates coordinates and speed, parses GPX/GeoJSON, and uses GeographicLib to interpolate routes by distance.
- `static/app.js` owns map editing and presents server state. It does not schedule route points or store backend target coordinates in a separate request.

The one-device limit is intentional. pymobiledevice3's userspace tunnel supports one tunnel per process. Switching devices requires a completed disconnect, and every subsequent mutation includes the current session ID. This prevents an old browser tab from sending a location command to a newly selected phone.

## Issue mapping

| Upstream report | Change | Verification boundary |
| --- | --- | --- |
| [#172: playback stops after repeated updates](https://github.com/davesc63/GeoPort/issues/172) | Reuse a persistent channel; serialize updates; stop on failure; close owned resources. | 500-update fake-device regression plus timeout and cancellation tests. The original reporter's physical failure is not reproduced. |
| [#185: custom speed not saved](https://github.com/davesc63/GeoPort/issues/185) | Send a validated numeric speed in the playback request. | Unit and browser checks preserve fractional custom speed. |
| [#137: jumping between markers](https://github.com/davesc63/GeoPort/issues/137) | Interpolate geodesic segments at a nominal 0.5-second interval using elapsed monotonic time. | Intermediate coordinates, boundaries, and date-line tests. |
| [#189: discovered device absent in UI](https://github.com/davesc63/GeoPort/issues/189) | Keep failed device records selectable and isolate per-device discovery errors. | Fake discovery test with one healthy and one inaccessible device. No claim that this resolves that reporter's exact pairing problem. |
| [#167: missing requirements](https://github.com/davesc63/GeoPort/issues/167) | pyproject.toml, uv.lock, package entry point, wheel/sdist, CI matrix. | Locked install and wheel/sdist build on Windows. |
| [#190: location resets after disconnection](https://github.com/davesc63/GeoPort/issues/190) | Document the OS/session limitation and expose disconnection honestly. | No persistence workaround or claim of an OS-level fix. |

Additional fixes: remove the coordinate-store/apply request race, return errors with HTTP status codes, await service updates before success, reject stale sessions, remove analytics and network calls from initial page rendering, use verified TLS and bounded fuel requests, remove duplicate templates and unused legacy paths.

## API

All mutations require the local page's `X-GeoPort-Token`. Except for connect/import, they also require the active `session_id` in their JSON body. Status and successful device operations return the current session object. Errors use `{"error":{"code":"…","message":"…"}}` with a non-2xx HTTP status.

| Method and path | Request / purpose |
| --- | --- |
| GET `/api/devices` | Discover devices without automatically enabling Wi-Fi or prompting pairing. |
| GET `/api/session` | Status, device, session ID, last accepted coordinates, playback progress, error. |
| POST `/api/connect` | `{"device_id":"…"}`; pair, prepare image, open the session. |
| POST `/api/disconnect` | Restore GPS request, close channel and tunnel, discard identity. |
| POST `/api/location` | `{"session_id":"…","point":[37.77,-122.42]}`. |
| DELETE `/api/location` | Stop playback and request GPS restoration. |
| POST `/api/playback` | `{"session_id":"…","points":[[37.77,-122.42],[37.78,-122.41]],"speed_kmh":7.25}`. |
| POST `/api/playback/pause` or `/resume` | Pause at the last accepted point or resume from that distance. |
| POST `/api/wifi` | Explicitly enable Wi-Fi lockdown connections on the paired device. |
| POST `/api/import` | Multipart `file`, GPX or GeoJSON; returns routes and markers. |
| GET `/api/fuel?region=All` | Optional fuel-price fetch, cached for five minutes. |

## Release gate: physical tests still required

- [ ] Windows, macOS, and Linux USB connection on representative iOS 17.4+, 18, 26, and 27 builds.
- [ ] First pairing and Developer Mode rejection/recovery with passcode retained.
- [ ] First developer image download, personalization, and reuse of a mounted image.
- [ ] At least 500 physical location updates and a 30-minute route; watch connection counts and memory.
- [ ] Custom speed, pause/resume, restore, reconnect, and device switching.
- [ ] Unplug USB mid-update; lose Wi-Fi; lock the phone; sleep/wake the computer.
- [ ] Confirm on the device that restore succeeds after normal disconnect and Ctrl+C.
- [ ] Verify error recovery on the user's exact iPhone 13 Pro / iOS 27 Public Beta build.

Automated tests prove application behavior against a fake adapter and check the pinned API's imports and async signatures. They cannot certify Apple's services or a particular beta. A failed restore or process crash may leave a simulated location until the phone resets it or the user reconnects and clears it.

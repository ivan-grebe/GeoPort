# GeoPort troubleshooting

## No devices appear

Unlock the phone, reconnect USB, and refresh. On Windows, confirm Apple's device software can see it. On Linux, check usbmuxd. GeoPort reports device-service errors instead of treating them as an empty list.

A device whose information cannot be read stays selectable. Use **Connect** to accept a pairing prompt. One inaccessible device does not hide the others.

## Developer Mode is required

Enable it in **Settings → Privacy & Security → Developer Mode**. Finish the restart and confirmation. Reconnect afterward. GeoPort does not remove the passcode, force a restart, or automate this setting.

## Preparing developer services fails

Initial setup may download and personalize a developer image. Check internet access and that Developer Mode is enabled. If a newer iOS build changes developer services, pymobiledevice3 may need an update. Replacing the dependency without checking its API and testing a physical device is not sufficient.

Downloads are cancellable and only complete images enter the cache. If GeoPort reports an invalid image cache, close GeoPort and use this command from the repository to print its exact location:

```sh
uv run python -c "from pymobiledevice3.common import get_home_folder; print(get_home_folder() / 'geoport-ddi')"
```

Delete only that `geoport-ddi` folder, then reconnect to download a fresh image. Keep the parent folder and pairing records.

If a timed-out setup is still closing, wait before reconnecting. GeoPort blocks overlapping retries. If cleanup remains stuck or reports a failure, restart GeoPort.

## Wi-Fi does not appear

Pair over USB and enable Wi-Fi connections in GeoPort. Use the same local network; guest isolation and blocked mDNS can prevent discovery. Unlock the phone while refreshing. Wi-Fi availability varies by Apple device services, host OS, and network configuration.

No automatic transport handoff is promised. Disconnect in GeoPort before unplugging, then refresh and reconnect.

## Location updates stop or a connection is lost

Playback stops when a device command fails or the connection reports disconnection. GeoPort clears its connection state and releases resources. Unlock the device, reconnect, and use **Restore GPS** before restarting your route. It does not silently resume a route after reconnecting.

The filled map point is the last position successfully sent, not a live reading of the phone's real GPS. A success message means the developer service call completed. Check the device to verify the resulting location.

## Does the location remain after unplugging or closing the computer?

There is no guarantee. Recent iOS versions can restore the real location when the developer session ends. Wi-Fi still needs the computer running and reachable. See [the separate phone-only investigation](docs/phone-only-research.md).

## Can I use an older iOS version?

This development edition targets iOS 17.4+. Earlier custom driver and tunnel paths were removed instead of carrying untested legacy code into the new session model.

## Can I use this without a map or fuel service?

Yes. Enter latitude and longitude directly. Leaflet assets are bundled, but map tiles and place searches require their external providers. Fuel prices load only when requested. None of those services is required by the location API.

## Report a problem

Include the GeoPort version, host OS, iPhone model, full iOS version/build, transport, exact error, and whether it happened during connect, set, play, pause, restore, or disconnect. Remove device identifiers and pairing data from any logs you share.

Do not report this development edition as an upstream 4.0.2 binary. It has a separate architecture and has not yet been certified on physical hardware.

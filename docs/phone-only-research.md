# Phone-only location simulation

Reviewed: **2026-09-05**. Target: **iPhone 13 Pro, iOS 27 Public Beta**. The exact iOS build number was not supplied.

Changing simulated location away from a computer appears feasible with existing on-device tools. Reliable cellular-only use remains unverified on this device and beta.

This is a review of project documentation and releases. No software was installed, device services contacted, or device settings changed.

## Documented capabilities

| Project | What its documentation establishes | What remains unverified |
| --- | --- | --- |
| [StikDebug](https://github.com/StikDebug/StikDebug) | Includes device location simulation. Lists iOS 17.4+ support, with a compatibility category for 26.0+. Requires a valid pairing file and a local loopback VPN. | Location simulation on this exact iPhone and iOS 27 Public Beta; uninterrupted background operation. |
| [StikPair](https://github.com/StikDebug/StikPair) | Creates pairing files on-device using iOS 27+ wireless pairing through the device's Developer Mode pairing interface. | Whether its pairing file successfully supports the complete location-simulation workflow on the user's exact build. |
| [TLocation](https://github.com/truongkma/t-location) | A location-focused StikDebug derivative. Supports setting and clearing simulated locations and implements background keep-alive. | Reliability on this exact beta, including prolonged use after leaving Wi-Fi. |

StikDebug is no longer available through the App Store. Its documented installation options include a signed or sideloaded IPA and building from source. Its latest listed release at review was [3.1.10](https://github.com/StikDebug/StikDebug/releases).

TLocation has published releases; the latest listed at review was [1.4.3](https://github.com/truongkma/t-location/releases). Its narrower interface may suit location testing, but it uses StikDebug's communication core.

## Network and persistence limits

TLocation explicitly requires joining a Wi-Fi network when starting simulation. The network need not provide internet; another phone's hotspot can work. Its documentation says cellular-only startup does not work on recent iOS builds. It only suggests that an existing session may survive brief network changes while the VPN remains active. [TLocation requirements](https://github.com/truongkma/t-location#requirements)

StikDebug's troubleshooting guidance also associates heartbeat failures with Wi-Fi, VPN, or pairing problems. It does not establish reliable cellular-only location simulation. [StikDebug documentation](https://github.com/StikDebug/StikDebug)

TLocation describes background keep-alive using silent audio and low-accuracy location activity. This is an implementation claim, not a guarantee across screen locking, force-quitting, rebooting, or network loss. [TLocation features](https://github.com/truongkma/t-location#features)

The official pairing guide warns that OS updates, resets, and other events can invalidate pairing files. An on-device pairing option may ease recovery, but does not eliminate it. [Pairing guide](https://github.com/StikDebug/StikDebug-Guide/blob/main/pairing_file.md)

## Setup prerequisites

- An installed and signed copy of the selected app, with a way to keep its signing valid.
- A valid pairing file for this device. StikPair documents on-device creation for iOS 27+; installation remains a separate prerequisite.
- The required local loopback VPN, which lets the app communicate with developer services on the same phone.
- A joined Wi-Fi network for the documented TLocation startup path.

Sources: [StikDebug requirements](https://github.com/StikDebug/StikDebug#requirements), [StikPair requirements](https://github.com/StikDebug/StikPair#requirements), [TLocation requirements](https://github.com/truongkma/t-location#requirements).

## Manual validation checklist

Use the user's own device and record each result separately. These checks have **not** been performed.

- [ ] Record the complete iOS version/build, app version, installation method, and VPN version.
- [ ] With the computer disconnected and Wi-Fi joined, establish the session and set a test coordinate.
- [ ] Verify that a location display receives that coordinate; change it again and verify the second update.
- [ ] Clear simulation and verify that the real location returns.
- [ ] Repeat a session with the app backgrounded and screen locked; check at 5, 15, and 30 minutes.
- [ ] Start on Wi-Fi, then leave Wi-Fi while keeping the VPN active. Record whether the existing simulation persists and whether a new coordinate can be applied.
- [ ] Separately try starting a fresh session on cellular alone. Record the actual outcome; documentation does not support promising success.
- [ ] Check recovery after stopping the VPN, terminating the app, and rebooting, recording whether pairing or setup must be repeated.

StikDebug is the best initial candidate to evaluate because it is the upstream project supplying TLocation's core. Treat successful pairing, successful simulation, and persistence as separate results. No exact-device compatibility claim should be made until the checks above pass.

"""Errors shared by HTTP handlers and the device worker."""


class GeoPortError(Exception):
    def __init__(self, message: str, code: str = "invalid_request", status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status


def device_error(exc: Exception) -> GeoPortError:
    if isinstance(exc, GeoPortError):
        return exc
    name = type(exc).__name__
    if isinstance(exc, TimeoutError):
        return GeoPortError(
            "The device did not respond in time. Unlock it, check the connection, and reconnect.",
            "device_timeout",
            504,
        )
    if name in {
        "NotTrustedError",
        "NotPairedError",
        "PairingError",
        "PasswordRequiredError",
        "UserDeniedPairingError",
        "PairingDialogResponsePendingError",
    }:
        return GeoPortError(
            "Unlock your device and accept Trust This Computer over USB, then reconnect.",
            "pairing_required",
            409,
        )
    if name in {"DeveloperModeIsNotEnabledError", "DeviceHasPasscodeSetError"}:
        return GeoPortError(
            "Enable Developer Mode in Settings → Privacy & Security on your device, "
            "complete its restart and confirmation, then reconnect. Keep your passcode enabled.",
            "developer_mode_required",
            409,
        )
    if name in {"ConnectionFailedToUsbmuxdError", "MuxException"}:
        return GeoPortError(
            "Apple's device service is unavailable. On Windows install Apple Devices or iTunes; "
            "on Linux start usbmuxd. Then refresh the device list.",
            "device_service_unavailable",
            503,
        )
    if name in {"InvalidServiceError", "StartServiceError", "NotMountedError"}:
        return GeoPortError(
            "The developer service is unavailable. Check Developer Mode and internet access "
            "for the developer image. This iOS build may need a pymobiledevice3 update.",
            "developer_service_unavailable",
            503,
        )
    return GeoPortError(
        f"Device communication failed ({name}). Check the connection and reconnect. "
        "If a simulated location remains, reconnect and select Restore GPS.",
        "device_unavailable",
        503,
    )

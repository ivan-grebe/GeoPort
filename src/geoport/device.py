"""The only module that knows pymobiledevice3's device and tunnel APIs."""

import asyncio
import logging
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass

from packaging.version import Version
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.remote.rsd_tunnel import PreferredRsdTunnel
from pymobiledevice3.services.amfi import AmfiService
from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation
from pymobiledevice3.services.mobile_image_mounter import (
    PersonalizedImageMounter,
)
from pymobiledevice3.usbmux import list_devices

from .errors import GeoPortError, device_error
from .images import ImageCache

logger = logging.getLogger(__name__)


@asynccontextmanager
async def open_lockdown(**kwargs):
    client = await create_using_usbmux(**kwargs)
    try:
        yield client
    finally:
        await client.close()


@asynccontextmanager
async def setup_step(label):
    try:
        yield
    except Exception as exc:
        error = device_error(exc)
        raise GeoPortError(f"{label}: {error}", error.code, error.status) from exc


@dataclass
class DeviceConnection:
    info: dict
    lockdown: object
    simulation: object
    dvt: object

    async def set(self, lat, lon):
        await self.simulation.set(lat, lon)

    async def clear(self):
        await self.simulation.clear()

    async def enable_wifi(self):
        await self.lockdown.set_enable_wifi_connections(True)

    async def wait_disconnected(self):
        await self.dvt.dtx.wait_disconnected()


class MobileDeviceBackend:
    def __init__(self):
        self.images = ImageCache()
        self.pending_cleanup = set()
        self.cleanup_failed = False

    def _check_cleanup(self):
        if self.cleanup_failed:
            raise GeoPortError(
                "Device setup could not close cleanly. Restart GeoPort before reconnecting.",
                "cleanup_failed",
                503,
            )
        if self.pending_cleanup:
            raise GeoPortError(
                "Previous device setup is still closing. Wait before reconnecting. "
                "If it remains stuck, restart GeoPort.",
                "cleanup_pending",
                409,
            )

    async def _enter(self, stack, context):
        # Some dependency factories catch Exception, but not CancelledError, before
        # returning their resource. Shield that acquisition and own any late result.
        opening = asyncio.create_task(context.__aenter__())
        try:
            result = await asyncio.shield(opening)
        except asyncio.CancelledError:

            async def finish_and_close():
                try:
                    await opening
                except Exception:
                    return
                await context.__aexit__(None, None, None)

            cleanup = asyncio.create_task(finish_and_close(), name="device-setup-cleanup")
            self.pending_cleanup.add(cleanup)

            def completed(task):
                self.pending_cleanup.discard(task)
                if not task.cancelled() and task.exception():
                    self.cleanup_failed = True
                    logger.warning(
                        "Late device setup cleanup failed: %s", type(task.exception()).__name__
                    )

            cleanup.add_done_callback(completed)
            raise
        stack.push_async_exit(context)
        return result

    async def close(self):
        if self.pending_cleanup:
            await asyncio.gather(*self.pending_cleanup, return_exceptions=True)

    async def discover(self):
        self._check_cleanup()
        async with asyncio.timeout(10):
            devices = await list_devices()

        async def inspect(device):
            info = {
                "id": device.serial,
                "name": "iOS device",
                "ios": "Unknown",
                "transports": [device.connection_type],
                "problem": None,
            }
            try:
                async with asyncio.timeout(5):
                    async with AsyncExitStack() as stack:
                        lockdown = await self._enter(
                            stack,
                            open_lockdown(
                                serial=device.serial,
                                connection_type=device.connection_type,
                                autopair=False,
                            ),
                        )
                        info.update(
                            name=lockdown.all_values.get("DeviceName", "iOS device"),
                            ios=lockdown.product_version,
                        )
            except Exception as exc:
                # An untrusted or locked device remains selectable so Connect can pair it.
                info["problem"] = str(device_error(exc))
            return info

        found = {}
        for item in await asyncio.gather(*(inspect(d) for d in devices)):
            if item["id"] not in found:
                found[item["id"]] = item
            else:
                previous = found[item["id"]]
                transports = sorted(set(previous["transports"] + item["transports"]))
                if not item["problem"]:
                    previous.update(item)
                previous["transports"] = transports
        return list(found.values())

    @asynccontextmanager
    async def connect(self, device_id):
        self._check_cleanup()
        async with AsyncExitStack() as stack:
            async with setup_step("Pairing and Developer Mode"):
                lockdown = await self._enter(
                    stack,
                    open_lockdown(
                        serial=device_id,
                        autopair=True,
                        pair_timeout=30,
                    ),
                )
                if lockdown.udid != device_id:
                    raise GeoPortError("The connected device does not match your selection.")
                if Version(lockdown.product_version) < Version("17.4"):
                    raise GeoPortError(
                        "This edition targets iOS 17.4 and newer. Earlier custom tunnel paths "
                        "are no longer included.",
                        "unsupported_ios",
                        409,
                    )
                if not await lockdown.get_developer_mode_status():
                    async with setup_step("Revealing Developer Mode"):
                        await AmfiService(lockdown).reveal_developer_mode_option_in_ui()
                    raise GeoPortError(
                        "Developer Mode is now visible in Settings → Privacy & Security. "
                        "Enable it, finish the "
                        "restart and confirmation, then reconnect. Keep your passcode enabled.",
                        "developer_mode_required",
                        409,
                    )
            async with setup_step("Preparing the developer image"):
                async with AsyncExitStack() as mounting:
                    mounter = await self._enter(mounting, PersonalizedImageMounter(lockdown))
                    if not await mounter.is_image_mounted("Personalized"):
                        image, manifest, trustcache = await self.images.get()
                        await mounter.mount(image, manifest, trustcache)
            async with setup_step("Opening the device tunnel"):
                rsd = await self._enter(stack, PreferredRsdTunnel(serial=device_id))
                if rsd.udid != device_id:
                    raise GeoPortError("The tunnel belongs to a different device.")
            async with setup_step("Opening location simulation"):
                dvt = await self._enter(stack, DvtProvider(rsd))
                simulation = await self._enter(stack, LocationSimulation(dvt))
            yield DeviceConnection(
                {
                    "id": device_id,
                    "name": lockdown.all_values.get("DeviceName", "iOS device"),
                    "ios": lockdown.product_version,
                },
                lockdown,
                simulation,
                dvt,
            )
